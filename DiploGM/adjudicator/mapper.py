import copy
import itertools
import math
import re
import sys
from xml.etree.ElementTree import ElementTree, Element, register_namespace
from xml.etree.ElementTree import tostring as elementToString

import numpy as np
import lxml.etree as etree

# from diplomacy.adjudicator import utils
# from diplomacy.map_parser.vector import config_svg as svgcfg

from DiploGM.map_parser.vector.utils import (
    clear_svg_element, get_element_color, get_svg_element,
    get_unit_coordinates, initialize_province_resident_data
)
from DiploGM.models import turn
from DiploGM.models.board import Board
from DiploGM.db.database import logger
from DiploGM.models.order import (
    Move, Hold, Core, Transform, ConvoyTransport, Support,
    RetreatMove, RetreatDisband, Build, Disband, TransformBuild, PlayerOrder
)
from DiploGM.models.player import Player
from DiploGM.models.province import ProvinceType, Province
from DiploGM.models.unit import Unit, UnitType

from DiploGM.map_parser.vector.transform import TransGL3
from DiploGM.map_parser.vector.vector import Parser

# TODO: Move this (and vector.py's copy to a central file)
NAMESPACE: dict[str, str] = {
    "inkscape": "{http://www.inkscape.org/namespaces/inkscape}",
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "svg": "http://www.w3.org/2000/svg",
}
SVG_CONFIG_KEY: str = "svg config"


# OUTPUTLAYER = "layer16"
# UNITLAYER = "layer17"


# if you make any rendering changes,
# make sure to sync them with mapper.js

class Mapper:
    def __init__(self, board: Board, restriction: Player | None = None, color_mode: str | None = None):
        register_namespace('', "http://www.w3.org/2000/svg")
        register_namespace('inkscape', "http://www.inkscape.org/namespaces/inkscape")
        register_namespace('sodipodi', "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd")
        register_namespace('xlink', "http://www.w3.org/1999/xlink")

        self.board: Board = board
        self.board_svg_data: dict = board.data[SVG_CONFIG_KEY]
        self.current_turn: turn.Turn = board.turn
        self.board_svg: ElementTree = etree.parse(self.board.data["file"])
        self.player_restriction: Player | None = None

        self._initialize_scoreboard_locations()

        # different colors
        if "color replacements" in self.board_svg_data:
            self.replacements = self.board_svg_data["color replacements"]
        else:
            self.replacements = None
        self.load_colors(color_mode)
        if color_mode is not None:
            self.replace_colors(color_mode)

        self.add_arrow_definition_to_svg(self.board_svg)

        clear_svg_element(self.board_svg, self.board_svg_data["starting_units"])

        self.cached_elements = {}
        for element_name in ["army", "fleet", "retreat_army", "retreat_fleet", "unit_output"]:
            self.cached_elements[element_name] = get_svg_element(
                self.board_svg, self.board_svg_data[element_name]
            )

        self.restriction = restriction
        visible_provinces = (self.board.get_visible_provinces(restriction)
                             if restriction else self.board.provinces)
        self.adjacent_provinces: set[str] = {p.name for p in visible_provinces}

        # TODO: Switch to passing the SVG directly, as that's simpiler (self.svg = draw_units(svg)?)
        self._draw_units()
        self._color_provinces()
        self._color_centers()
        self.draw_side_panel(self.board_svg)


        self._moves_svg = copy.deepcopy(self.board_svg)
        self.cached_elements["unit_output_moves"] = get_svg_element(
            self._moves_svg, self.board_svg_data["unit_output"]
        )

        self.state_svg = copy.deepcopy(self.board_svg)
        self.clean_layers(self.state_svg)

        self._highlight_retreating_units(self.state_svg)

    def clean_layers(self, svg: ElementTree):
        """Clears layers that we won't need in the final display map."""
        for element_name in self.board_svg_data["delete_layer"]:
            clear_svg_element(svg, self.board_svg_data[element_name])

    def is_moveable(self, unit: Unit):
        """Checks if a unit is moveable."""
        if unit.province.name not in self.adjacent_provinces:
            return False
        if unit.player is None:
            return False
        if self.player_restriction and unit.player.name != self.player_restriction.name:
            return False
        if self.current_turn.is_retreats() and unit.province.dislodged_unit != unit:
            return False
        return True

    def draw_moves_and_retreats(self, arrow_layer: Element, current_turn: turn.Turn, movement_only: bool):
        """Draws move and retreat arrows."""
        units = sorted(self.board.units, key=lambda unit: 0 if unit.order is None else unit.order.display_priority)
        for unit in units:
            if not self.is_moveable(unit):
                continue

            # Only show moves that succeed if requested
            if movement_only and not (
                isinstance(unit.order, (RetreatMove, Move)) and not unit.order.has_failed):
                continue

            unit_locs = unit.province.all_rets if current_turn.is_retreats() else unit.province.all_locs
            unit_locs = self._get_unit_coordinates(unit, unit_locs)

            # TODO: Maybe there's a better way to handle convoys?
            if isinstance(unit.order, (RetreatMove, Move, Support)):
                new_locs = []
                if unit.unit_type not in unit.order.destination.all_locs:
                    e_list = next(iter(unit.order.destination.all_locs.values()))
                elif unit.order.destination_coast:
                    e_list = unit.order.destination.all_locs[unit.order.destination_coast]
                else:
                    e_list = unit.order.destination.all_locs[unit.unit_type]

                # Unspecified coast, so default to army location
                if isinstance(e_list, dict):
                    e_list = unit.order.destination.all_locs[UnitType.ARMY]
                for endpoint in e_list:
                    new_locs += [self._normalize(self.get_closest_loc(unit_locs, endpoint))]
                unit_locs = new_locs
            try:
                for loc in unit_locs:
                    val = self._draw_order(unit, loc, current_turn)
                    if val is None:
                        continue
                    # if something returns, that means it could potentially go across the edge
                    # copy it 3 times (-1, 0, +1)
                    lval = copy.deepcopy(val)
                    rval = copy.deepcopy(val)
                    lval.attrib["transform"] = f"translate({-self.board.data['svg config']['map_width']}, 0)"
                    rval.attrib["transform"] = f"translate({self.board.data['svg config']['map_width']}, 0)"

                    arrow_layer.append(lval)
                    arrow_layer.append(rval)
                    arrow_layer.append(val)
            except Exception as err:
                logger.error("Drawing move failed for %s", unit, exc_info=err)

    def draw_moves_map(self,
                       current_turn: turn.Turn,
                       player_restriction: Player | None,
                       movement_only: bool = False) -> tuple[bytes, str]:
        """Draws the map with orders.
        If player_restriction is not None, then only show orders for that player.
        If movement_only is True, then only show moves that succeed (no failed moves or supports/convoys)."""
        logger.info("mapper.draw_moves_map")

        self._reset_moves_map()
        self.player_restriction = player_restriction
        self.current_turn = current_turn

        t = self._moves_svg.getroot()
        assert t is not None
        arrow_layer = get_svg_element(self._moves_svg, self.board_svg_data["arrow_output"])
        if arrow_layer is None:
            raise ValueError("Arrow layer not found in SVG")

        if not current_turn.is_builds():
            self.draw_moves_and_retreats(arrow_layer, current_turn, movement_only)
        else:
            for player in self.board.players if player_restriction is None else {player_restriction}:
                for build_order in player.build_orders:
                    if isinstance(build_order, PlayerOrder) and build_order.province.name in self.adjacent_provinces:
                        self._draw_player_order(player, build_order)

        self.draw_side_panel(self._moves_svg)

        self.clean_layers(self._moves_svg)

        svg_file_name = f"{str(self.board.turn).replace(' ', '_')}_moves_map.svg"
        return elementToString(t, encoding="utf-8"), svg_file_name

    def draw_gui_map(self, current_turn: turn.Turn, player_restriction: Player | None) -> tuple[bytes, str]:
        self.player_restriction = player_restriction
        self.current_turn = current_turn
        self._reset_moves_map()
        self.clean_layers(self._moves_svg)
        root = self._moves_svg.getroot()
        if root is None:
            raise ValueError("SVG root is None")
        clear_svg_element(self._moves_svg, self.board_svg_data["sidebar"])
        clear_svg_element(self._moves_svg, self.board_svg_data["power_banners"])
        with open("DiploGM/adjudicator/mapper.js", 'r', encoding='utf-8') as f:
            js = f.read()

        locdict = {}

        for province in self.board.provinces:
            coast = None
            if province.unit:
                unit_type = province.unit.unit_type
                coast = province.unit.coast
            else:
                unit_type = UnitType.FLEET if province.type == ProvinceType.SEA else UnitType.ARMY
            locdict[province.name] = list(province.get_primary_unit_coordinates(unit_type, coast))
            for coast in province.get_multiple_coasts():
                locdict[province.get_name(coast)] = list(province.get_primary_unit_coordinates(UnitType.FLEET, coast))

        script = etree.Element("script")

        coast_to_province = {}
        for province in self.board.provinces:
            for coast in province.get_multiple_coasts():
                coast_to_province[province.get_name(coast)] = province.name

        province_to_unit_type = {}
        for province in self.board.provinces:
            s = None
            if province.name not in self.adjacent_provinces:
                s = '?'
            elif province.unit:
                s = 'f' if province.unit.unit_type == UnitType.FLEET else 'a'
            province_to_unit_type[province.name] = s

        province_to_province_type = {}
        for province in self.board.provinces:
            if province.type == ProvinceType.SEA:
                province_type = 'sea'
            elif province.type == ProvinceType.ISLAND:
                province_type = 'island'
            elif province.type == ProvinceType.LAND:
                province_type = 'land'
            else:
                raise ValueError(f"Unknown province type {province.type} for province {province.name}")
            province_to_province_type[province.name] = province_type

        immediate = [unit.province.get_name(unit.coast)
                     for unit in self.board.units
                     if self.is_moveable(unit)]

        script.text = js % (str(locdict), self.board_svg_data, coast_to_province,
                            province_to_unit_type, province_to_province_type, immediate)
        root.append(script)

        coasts = get_svg_element(root, self.board_svg_data["coast_markers"])
        def get_text_coordinate(e : etree.Element) -> tuple[float, float]:
            trans = TransGL3(e)
            x, y = e.attrib["x"], e.attrib["y"]
            assert x is not None and y is not None
            return trans.transform(tuple([float(x), float(y)] + np.array([3.25, -3.576 / 2])))

        def match(p: Province, e: Element, _:str | None):
            e.set("onclick", f'obj_clicked(event, "{p} {e[0].text}", false)')
            e.set("oncontextmenu", f'obj_clicked(event, "{p} {e[0].text}", false)')

        if coasts is not None:
            initialize_province_resident_data(self.board.provinces, coasts, get_text_coordinate, match)

        def get_sc_coordinates(supply_center_data: Element) -> tuple[float | None, float | None]:
            circles = supply_center_data.findall(".//svg:circle", namespaces=NAMESPACE)
            if not circles:
                return None, None
            cx = circles[0].get("cx")
            cy = circles[0].get("cy")
            if cx is None or cy is None:
                return None, None
            base_coordinates = float(cx), float(cy)
            trans = TransGL3(supply_center_data)
            return trans.transform(base_coordinates)

        def set_province_supply_center(p: Province, e: Element, _:str | None) -> None:
            e.set("onclick", f'obj_clicked(event, "{p.name}", false)')
            e.set("oncontextmenu", f'obj_clicked(event, "{p.name}", false)')

        supply_center_icons = get_svg_element(root, self.board_svg_data["supply_center_icons"])
        if supply_center_icons is None:
            raise ValueError("Supply center icons layer not found in SVG")
        initialize_province_resident_data(self.board.provinces,
                                          supply_center_icons,
                                          get_sc_coordinates,
                                          set_province_supply_center)

        for layer_name in ("land_layer", "island_borders", "island_ring_layer", "island_fill_layer", "sea_borders"):
            layer = get_svg_element(root, self.board_svg_data[layer_name])
            if layer is None:
                raise ValueError(f"Layer {layer_name} not found in SVG")
            for province_data in layer:
                name = Parser.get_province_name(province_data)
                province_data.set("onclick", f'obj_clicked(event, "{name}", false)')
                province_data.set("oncontextmenu", f'obj_clicked(event, "{name}", false)')


        return elementToString(root, encoding="utf-8"), f"{str(self.board.turn).replace(' ', '_')}_gui.svg"


    def load_colors(self, color_mode: str | None = None) -> None:
        """Loads player colors based on the color mode."""
        self.player_colors = {
            "None": "ffffff",
            "Neutral": self.board_svg_data.get("neutral", "ffffff")
        }
        for player in self.board.players:
            if color_mode is not None and player.color_dict and color_mode in player.color_dict:
                color = player.color_dict[color_mode]
            else:
                color = player.render_color
            self.player_colors[player.name] = color
        neutral_color = self.board_svg_data.get("neutral", "ffffff")
        if isinstance(neutral_color, dict):
            neutral_color = neutral_color.get(color_mode, neutral_color.get("standard", "ffffff"))
        self.player_colors["Neutral"] = neutral_color

        #TODO: draw dual monarchies as stripes
        if color_mode == "empires":
            for player in self.board.players:
                for vassal in player.vassals or []:
                    self.player_colors[vassal.name] = self.player_colors[player.name]
                    for subvassal in vassal.vassals or []:
                        self.player_colors[subvassal.name] = self.player_colors[player.name]
        elif color_mode == "kingdoms":
            for player in self.board.players:
                if player.liege or not player.vassals:
                    continue
                for vassal in player.vassals:
                    self.player_colors[vassal.name] = self.player_colors[player.name]

        neutral_colors = self.board_svg_data["neutral"]
        if isinstance(neutral_colors, str):
            self.neutral_color = neutral_colors
        else:
            self.neutral_color = neutral_colors.get(color_mode, neutral_colors["standard"])

        self.clear_seas_color = self.board_svg_data["default_sea_color"]
        if (self.replacements is not None
            and self.clear_seas_color in self.replacements
            and color_mode in self.replacements[self.clear_seas_color]):
            self.clear_seas_color = self.replacements[self.clear_seas_color][color_mode]

    def replace_colors(self, color_mode: str) -> None:
        """Replaces colors in the SVG based on the color mode."""
        other_fills = get_svg_element(self.board_svg, self.board_svg_data["other_fills"])
        background = get_svg_element(self.board_svg, self.board_svg_data["background"])
        if self.replacements is not None:
            elements_to_process = []
            if other_fills is not None:
                elements_to_process.extend(other_fills)
            if background is not None:
                elements_to_process.extend(background)
            for element in elements_to_process:
                color = get_element_color(element)
                if color in self.replacements:
                    if color_mode in self.replacements[color]:
                        self._color_element(element, self.replacements[color][color_mode])
                elif color_mode == "dark":
                    self._color_element(element, "ffffff")



        # Difficult to detect correctly using either geometry or province names
        # Marking manually would work, but for all svgs is time consuming. TODO

        # get_svg_element(self.board_svg, self.board_svg_data["starting_units"])
        # province_names = get_svg_element(self.board_svg, self.board_svg_data["province_names"]).getchildren()
        # for text_box in province_names:
        #     try:
        #         text = text_box[0].text.lower()
        #     except:
        #         continue
        #     text = re.sub("[\\s\n]+", " ", text )
        #     if text in self.board.name_to_province:
        #         p = self.board.name_to_province[text]
        #         if p.type == ProvinceType.ISLAND or p.type == ProvinceType.SEA:
        #             self.color_element(text_box, "ffffff")
        #     else:
        #         print(text)

    def draw_current_map(self) -> tuple[bytes, str]:
        """Draws the map without orders"""
        logger.info("mapper.draw_current_map")
        svg_file_name = f"{str(self.board.turn).replace(' ', '_')}_map.svg"
        root = self.state_svg.getroot()
        if root is None:
            raise ValueError("SVG root is None")
        return elementToString(root, encoding="utf-8"), svg_file_name

    def draw_side_panel(self, svg: ElementTree) -> None:
        """Draws the side panel with the date and scoreboard."""
        self._draw_side_panel_date(svg)
        self._draw_side_panel_scoreboard(svg)

    def _draw_power_banner(self, power_element: Element, player: Player,
                           banner_index: int, high_player_count: bool) -> bool:
        if len(power_element) == 0:
            return False
        initial_pretransform_coordinates = (float(power_element[0].get("x", 0)), float(power_element[0].get("y", 0)))
        banner_coordinates = TransGL3(power_element).transform(initial_pretransform_coordinates)
        if high_player_count and banner_coordinates != self.scoreboard_power_locations[banner_index]:
            return False
        if not high_player_count and get_element_color(power_element[0]) != player.default_color:
            return False
        player_data = self.board.data["players"][player.name]
        if player_data.get("hidden") == "true":
            power_element.clear()
            return True

       # TODO: Add support for chaos "points" and perhaps simplify this whole thing
        name_index = self.board_svg_data.get("power_name_index", 1)
        sc_index = self.board_svg_data.get("power_sc_index", 5)
        iscc_index = self.board_svg_data.get("power_iscc_index", 6)
        vscc_index = self.board_svg_data.get("power_vscc_index", 7)

        self._color_element(power_element[0], self.player_colors[player.name])
        new_translation = (self.scoreboard_power_locations[banner_index][0] - initial_pretransform_coordinates[0],
                            self.scoreboard_power_locations[banner_index][1] - initial_pretransform_coordinates[1])
        power_element.set("transform", f"translate({new_translation[0]}, {new_translation[1]})")
        if high_player_count or player_data.get("nickname"):
            power_element[name_index][0].text = player.get_name()
            # Fix for Poland-Lithuanian Commonwealth
            if len(power_element[name_index]) > 1:
                power_element[name_index][1].text = ""
                power_element[name_index].set("y", "237.67107")
                power_element[name_index][0].set("y", "237.67107")
                style = power_element[name_index].get("style")
                assert style is not None
                style = re.sub(r"font-size:[0-9.]+px", "font-size:42.6667px", style)
                power_element[name_index].set("style", style)
        power_element[sc_index][0].text = (str(len(player.centers))
            if (self.restriction is None or self.restriction == player) else "???")
        if iscc_index > -1:
            power_element[iscc_index][0].text = str(player_data["iscc"])
        if self.board.data["victory_conditions"] == "classic" and vscc_index > -1:
            power_element[vscc_index][0].text = str(self.board.data["victory_count"])
        elif vscc_index > -1:
            power_element[vscc_index][0].text = str(player_data["vscc"])
        return True

    def _draw_side_panel_scoreboard(self, svg: ElementTree) -> None:
        """
        format is a list of each power; for each power, its children nodes are as follows:
        0: colored rectangle
        1: full name ("Dutch Empire", ...)
        2-4: "current", "victory", "start" text labels in that order
        5-7: SC counts in that same order
        """

        root = svg.getroot()
        if root is None:
            raise ValueError("SVG root is None")
        all_power_banners_element = get_svg_element(root, self.board_svg_data["power_banners"])
        if all_power_banners_element is None:
            return

        if self.board.fow and self.restriction is not None:
            # don't get info
            players = sorted(self.board.players, key=lambda sort_player: sort_player.name)
        else:
            players = self.board.get_players_sorted_by_score()
        players = sorted(players, key=lambda hidden_player:
                                  self.board.data["players"][hidden_player.name].get("hidden", "false") == "true")

        high_player_count = (len(self.board.players) > len(self.scoreboard_power_locations)
                             or self.board.data.get("vassals") == "enabled")
        for i, player in enumerate(self.board.get_players_sorted_by_score()):
            if i >= len(self.scoreboard_power_locations):
                break
            for power_element in all_power_banners_element:
                if self._draw_power_banner(power_element, player, i, high_player_count):
                    break

    def _draw_side_panel_date(self, svg: ElementTree) -> None:
        date = get_svg_element(svg, self.board_svg_data["season"])
        if date is None:
            return
        game_name = self.board.name
        name_text = "" if game_name is None else f"{game_name} — "
        # TODO: this is hacky; I don't know a better way
        date[0][0].text = name_text + str(self.board.turn)

    def _reset_moves_map(self):
        self._moves_svg = copy.deepcopy(self.board_svg)

    def _draw_order(self, unit: Unit, coordinate: tuple[float, float], current_turn: turn.Turn) -> None:
        order = unit.order
        if isinstance(order, Hold):
            self._draw_hold(coordinate, order.has_failed)
        elif isinstance(order, Core):
            self._draw_core(coordinate, order.has_failed)
        elif isinstance(order, Transform):
            self._draw_transform(coordinate, order.has_failed)
        elif isinstance(order, Move):
            # moves are just convoyed moves that have no convoys
            return self._draw_convoyed_move(unit, coordinate, order.has_failed)
        elif isinstance(order, Support):
            return self._draw_support(unit, coordinate, order.has_failed)
        elif isinstance(order, ConvoyTransport):
            self._draw_convoy(order, coordinate, order.has_failed)
        elif isinstance(order, RetreatMove):
            return self._draw_retreat_move(order, unit.unit_type, coordinate)
        elif isinstance(order, RetreatDisband):
            self._draw_force_disband(coordinate, self._moves_svg)
        else:
            if current_turn.is_moves():
                self._draw_hold(coordinate, False)
            else:
                self._draw_force_disband(coordinate, self._moves_svg)
            logger.debug("None order found: hold drawn. Coordinates: %s", coordinate)

    def _draw_player_order(self, player: Player, order: PlayerOrder):
        if isinstance(order, Build):
            self._draw_build(player, order)
        elif isinstance(order, Disband):
            assert order.province.unit is not None
            disbanding_unit: Unit = order.province.unit
            if disbanding_unit.coast:
                coord_list = order.province.all_locs[disbanding_unit.coast]
            else:
                coord_list = order.province.all_locs[disbanding_unit.unit_type]
            for coord in coord_list:
                self._draw_force_disband(coord, self._moves_svg)
        elif isinstance(order, TransformBuild):
            assert order.province.unit is not None
            transforming_unit: Unit = order.province.unit
            if transforming_unit.coast:
                coord_list = order.province.all_locs[transforming_unit.coast]
            else:
                coord_list = order.province.all_locs[transforming_unit.unit_type]
            for coord in coord_list:
                self._draw_transform(coord, False)
        else:
            logger.error("Could not draw player order %s", order)

    def _draw_hold(self, coordinate: tuple[float, float], has_failed: bool) -> None:
        element = self._moves_svg.getroot()
        assert element is not None
        drawn_order = self._create_element(
            "circle",
            {
                "cx": coordinate[0],
                "cy": coordinate[1],
                "r": self.board_svg_data["unit_radius"],
                "fill": "none",
                "stroke": "red" if has_failed else "black",
                "stroke-width": self.board_svg_data["order_stroke_width"],
            },
        )
        element.append(drawn_order)

    def _draw_core(self, coordinate: tuple[float, float], has_failed: bool) -> None:
        element = self._moves_svg.getroot()
        assert element is not None
        drawn_order = self._create_element(
            "rect",
            {
                "x": coordinate[0] - self.board_svg_data["unit_radius"],
                "y": coordinate[1] - self.board_svg_data["unit_radius"],
                "width": self.board_svg_data["unit_radius"] * 2,
                "height": self.board_svg_data["unit_radius"] * 2,
                "fill": "none",
                "stroke": "red" if has_failed else "black",
                "stroke-width": self.board_svg_data["order_stroke_width"],
                "transform": f"rotate(45 {coordinate[0]} {coordinate[1]})",
            },
        )
        element.append(drawn_order)

    def _draw_transform(self, coordinate: tuple[float, float], has_failed: bool) -> None:
        element = self._moves_svg.getroot()
        assert element is not None
        drawn_order = self._create_element(
            "rect",
            {
                "x": coordinate[0] - self.board_svg_data["unit_radius"],
                "y": coordinate[1] - self.board_svg_data["unit_radius"],
                "width": self.board_svg_data["unit_radius"] * 2,
                "height": self.board_svg_data["unit_radius"] * 2,
                "fill": "none",
                "stroke": "red" if has_failed else "black",
                "stroke-width": self.board_svg_data["order_stroke_width"],
            },
        )
        element.append(drawn_order)

    def _draw_retreat_move(self, order: RetreatMove, unit_type: UnitType, coordinate: tuple[float, float]) -> None:
        destination = self._loc_to_point(order.destination, unit_type, order.destination_coast, coordinate)
        if order.destination.unit:
            destination = self.pull_coordinate(coordinate, destination)
        order_path = self._create_element(
            "path",
            {
                "d": f"M {coordinate[0]},{coordinate[1]} L {destination[0]},{destination[1]}",
                "fill": "none",
                "stroke": "red",
                "stroke-width": self.board_svg_data["order_stroke_width"],
                "stroke-linecap": "round",
                "marker-end": "url(#redarrow)",
            },
        )
        return order_path

    def _path_helper(
        self, source: Province, destination: Province, current: Province, already_checked=()
    ) -> list[tuple[Province, Province]]:
        if current in already_checked:
            return []
        options = []
        new_checked = already_checked + (current,)
        for possibility in current.adjacent:
            if possibility.name not in self.adjacent_provinces:
                continue

            if possibility == destination:
                return [
                    (
                        current,
                        destination,
                    )
                ]
            if (
                possibility.can_convoy
                and possibility.unit is not None
                and (self.player_restriction is None or possibility.unit.player == self.player_restriction)
                and possibility.unit.unit_type == UnitType.FLEET
                and isinstance(possibility.unit.order, ConvoyTransport)
                and possibility.unit.order.source is source
                and possibility.unit.order.destination is destination
            ):
                options += self._path_helper(source, destination, possibility, new_checked)
        return list(map((lambda t: (current,) + t), options))

    def _draw_path(self, d: str, marker_end="arrow", stroke_color="black"):
        order_path = self._create_element(
            "path",
            {
                "d": d,
                "fill": "none",
                "stroke": stroke_color,
                "stroke-width": self.board_svg_data["order_stroke_width"],
                "stroke-linecap": "round",
                "marker-end": f"url(#{marker_end})",
            },
        )
        return order_path

    def _get_all_paths(self, unit: Unit) -> list[tuple[Province, Province]]:
        assert unit.order is not None and unit.order.destination is not None
        paths = self._path_helper(unit.province, unit.order.destination, unit.province)
        if not paths:
            return [(unit.province, unit.order.destination)]
        return paths

    # removes unnecessary convoys, for instance [A->B->C & A->C] -> [A->C]
    def _get_shortest_paths(self, args: list[tuple]) -> list[tuple]:
        args.sort(key=len)
        min_subsets = []
        for s in args:
            if not any(set(min_subset).issubset(s) for min_subset in min_subsets):
                min_subsets.append(s)

        return min_subsets

    def _draw_convoyed_move(self, unit: Unit, coordinate: tuple[float, float], has_failed: bool):
        def f(point: tuple[float, float]):
            return " ".join(map(str, point))

        def norm(point: tuple[float, float]) -> tuple[float, float]:
            return point / ((np.sum(np.array(point)**2)) ** 0.5)

        valid_convoys = self._get_all_paths(unit)
        # TODO: make this a setting
        if False:
            if len(valid_convoys):
                valid_convoys = valid_convoys[0:1]
        valid_convoys = self._get_shortest_paths(valid_convoys)
        for path in valid_convoys:
            p = [coordinate]
            start = coordinate
            for loc in path[1:]:
                p += [self._loc_to_point(loc, unit.unit_type, None, start)]
                start = p[-1]

            if path[-1].unit:
                p[-1] = self.pull_coordinate(p[-2], p[-1])

            p = np.array(p)

            # given surrounding points, generate a control point
            def g(point: np.ndarray) -> tuple[float, float]:
                centered = point[::2] - point[1]

                # TODO: possible div / 0 if the two convoyed points are in a straight line with the convoyer on one side
                vec = tuple(np.subtract(centered[0], norm(centered[1])))
                return norm(vec) * 30 + point[1]

            # this is a bit weird, because the loop is in-between two values
            # (S LO)(OP LO)(OP E)
            s = f"M {f(p[0])} C {f(p[1])}, "
            for x in range(1, len(p) - 1):
                s += f"{f(g(p[x-1:x+2]))}, {f(p[x])} S "

            s += f"{f(p[-2])}, {f(p[-1])}"
            stroke_color = "red" if has_failed else "black"
            marker_color = "redarrow" if has_failed else "arrow"
            return self._draw_path(s, marker_end = marker_color, stroke_color = stroke_color)

    def _draw_support(self, unit: Unit, coordinate: tuple[float, float], has_failed: bool) -> None:
        if not isinstance(unit.order, Support):
            raise ValueError("Trying to draw a non-support order as a support")
        order: Support = unit.order
        source: Province = order.source
        if source.unit is None:
            raise ValueError("Support order has no source unit")
        source_coord = self._loc_to_point(source, unit.unit_type, source.unit.coast, coordinate)
        if (isinstance(source.unit.order, Move)
            and source.unit.order.destination == order.destination
            and (not order.destination_coast
                 or source.unit.order.destination_coast == order.destination_coast)):
            dest_coast = source.unit.order.destination_coast
        else:
            dest_coast = order.destination_coast
        dest_coord = self._loc_to_point(order.destination, source.unit.unit_type, dest_coast, source_coord)
        marker_start = ""
        ball_type = "redball" if has_failed else "ball"
        arrow_type = "redarrow" if has_failed else "arrow"
        if order.destination.unit:
            if order.source == order.destination:
                dest_coord = self.pull_coordinate(coordinate, dest_coord, self.board_svg_data["unit_radius"])
            else:
                dest_coord = self.pull_coordinate(source_coord, dest_coord)
            # Draw hold around unit that can be support-held
            if (order.source == order.destination
                and isinstance(source.unit.order, (ConvoyTransport, Support))
                and self.is_moveable(source.unit)):
                for coord in source.all_locs[source.unit.coast if source.unit.coast else source.unit.unit_type]:
                    self._draw_hold(coord, False)

            # if two units are support-holding each other
            destorder = order.destination.unit.order

            if (
                isinstance(destorder, Support)
                and destorder.source == destorder.destination == unit.province
                and order.source == order.destination
                and (self.player_restriction is None
                     or order.destination.unit.player == self.player_restriction)
            ):
                # This check is so we only do it once, so it doesn't overlay
                # it doesn't matter which one is the origin & which is the dest
                if id(order.destination.unit) < id(unit):
                    return
                marker_start = f"url(#{ball_type})"
                # doesn't matter that v3 has been pulled, as it's still collinear
                coordinate = source_coord = self.pull_coordinate(
                    dest_coord, coordinate, self.board_svg_data["unit_radius"]
                )

        dasharray_size = 2.5 * self.board_svg_data["order_stroke_width"]
        drawn_order = self._create_element(
            "path",
            {
                "d": f"M {coordinate[0]},{coordinate[1]} " + \
                     f"Q {source_coord[0]},{source_coord[1]} " \
                     f"{dest_coord[0]},{dest_coord[1]}",
                "fill": "none",
                "stroke": "red" if has_failed else "black",
                "stroke-dasharray": f"{dasharray_size} {dasharray_size}",
                "stroke-width": self.board_svg_data["order_stroke_width"],
                "stroke-linecap": "round",
                "marker-start": marker_start,
                "marker-end": f"url(#{ball_type if order.source == order.destination else arrow_type})",
            },
        )
        return drawn_order

    def _draw_convoy(self, order: ConvoyTransport, coordinate: tuple[float, float], has_failed: bool) -> None:
        element = self._moves_svg.getroot()
        assert element is not None
        drawn_order = self._create_element(
            "circle",
            {
                "cx": coordinate[0],
                "cy": coordinate[1],
                "r": self.board_svg_data["unit_radius"] / 2,
                "fill": "none",
                "stroke": "red" if has_failed else "black",
                "stroke-width": self.board_svg_data["order_stroke_width"] * 2 / 3,
            },
        )
        element.append(drawn_order)

    def _draw_build(self, player, order: Build) -> None:
        element = self._moves_svg.getroot()
        assert element is not None
        build_location = order.province.get_primary_unit_coordinates(order.unit_type, order.coast)
        drawn_order = self._create_element(
            "circle",
            {
                "cx": build_location[0],
                "cy": build_location[1],
                "r": 10,
                "fill": "none",
                "stroke": "green",
                "stroke-width": self.board_svg_data["order_stroke_width"],
            },
        )

        self._draw_unit(Unit(order.unit_type, player, order.province, order.coast, None), use_moves_svg=True)
        element.append(drawn_order)

    def _draw_disband(self, coordinate: tuple[float, float], svg) -> None:
        element = svg.getroot()
        drawn_order = self._create_element(
            "circle",
            {
                "cx": coordinate[0],
                "cy": coordinate[1],
                "r": self.board_svg_data["unit_radius"],
                "fill": "none",
                "stroke": "red",
                "stroke-width": self.board_svg_data["order_stroke_width"],
            },
        )
        element.append(drawn_order)

    def _draw_force_disband(self, coordinate: tuple[float, float], svg) -> None:
        element = svg.getroot()
        cross_width = self.board_svg_data["order_stroke_width"] / (2**0.5)
        square_rad = self.board_svg_data["unit_radius"] / (2**0.5)
        # two corner and a center point. Rotate and concat them to make the correct object
        init = np.array(
            [
                (-square_rad + cross_width, -square_rad),
                (-square_rad, -square_rad + cross_width),
                (-cross_width, 0),
            ]
        )
        rotate_90 = np.array([[0, -1], [1, 0]])
        points = np.concatenate((init, init @ rotate_90, -init, -init @ rotate_90)) + coordinate
        drawn_order = self._create_element(
            "polygon",
            {
                "points": " ".join(map(lambda a: ",".join(map(str, a)), points)),
                "fill": "red",
            },
        )

        element.append(drawn_order)

    def _color_provinces(self) -> None:
        province_layer = get_svg_element(self.board_svg, self.board_svg_data["land_layer"])
        island_fill_layer = get_svg_element(self.board_svg, self.board_svg_data["island_fill_layer"])
        island_ring_layer = get_svg_element(self.board_svg, self.board_svg_data["island_ring_layer"])
        sea_layer = get_svg_element(self.board_svg, self.board_svg_data["sea_borders"])
        island_layer = get_svg_element(self.board_svg, self.board_svg_data["island_borders"])
        if sea_layer is None or island_layer is None or island_ring_layer is None:
            raise ValueError("Missing a layer in SVG!")

        visited_provinces: set[str] = set()

        for province_element in itertools.chain(province_layer or [], island_fill_layer or []):
            try:
                province = self._get_province_from_element_by_label(province_element)
            except ValueError as ex:
                print(f"Error during recoloring provinces: {ex}", file=sys.stderr)
                continue

            visited_provinces.add(province.name)
            color = self.neutral_color
            if province.name not in self.adjacent_provinces:
                color = self.board_svg_data["unknown"]
            elif province.owner:
                color = self.player_colors[province.owner.name]

            self._color_element(province_element, color)

        for province_element in itertools.chain(sea_layer, island_layer):
            try:
                province = self._get_province_from_element_by_label(province_element)
            except ValueError as ex:
                print(f"Error during recoloring provinces: {ex}", file=sys.stderr)
                continue

            if province.name in self.adjacent_provinces:
                self._color_element(province_element, self.clear_seas_color)

            visited_provinces.add(province.name)

        # Try to combine this with the code above? A lot of repeated stuff here
        for island_ring in island_ring_layer:
            try:
                province = self._get_province_from_element_by_label(island_ring)
            except ValueError as ex:
                print(f"Error during recoloring provinces: {ex}", file=sys.stderr)
                continue

            color = self.neutral_color
            if province.name not in self.adjacent_provinces:
                color = self.board_svg_data["unknown"]
            elif province.owner:
                color = self.player_colors[province.owner.name]
            self._color_element(island_ring, color, key="stroke")

        for province in self.board.provinces:
            if province.name not in visited_provinces and (self.board.fow or province.type != ProvinceType.SEA):
                print(f"Warning: Province {province.name} was not recolored by mapper!")

    def _color_centers(self) -> None:
        centers_layer = get_svg_element(self.board_svg, self.board_svg_data["supply_center_icons"])
        if centers_layer is None:
            raise ValueError("Supply Center layer not found in SVG")

        for center_element in centers_layer:
            try:
                province = self._get_province_from_element_by_label(center_element)
            except ValueError as ex:
                print(f"Error during recoloring centers: {ex}", file=sys.stderr)
                continue

            if not province.has_supply_center:
                print(f"Province {province.name} says it has no supply center, but it does", file=sys.stderr)
                continue

            if province.name not in self.adjacent_provinces:
                core_color = self.board_svg_data["unknown"]
                half_color = core_color
            else:
                core_color = self.player_colors[province.core.name] if province.core else "#ffffff"
                half_color = self.player_colors[province.half_core.name] if province.half_core else core_color
            # color = "#ffffff"
            # if province.core:
            #     color = province.core.color
            # elif province.half_core:
            #     # TODO: I tried to put "repeating-linear-gradient(white, {province.half_core.color})" here but that
            #     #  doesn't work. Doing this in SVG requires making a new pattern in defs which means doing a separate
            #     #  pattern for every single color, which would suck
            #     #  https://stackoverflow.com/questions/27511153/fill-svg-element-with-a-repeating-linear-gradient-color
            #     # ...it doesn't have to be stripes, that was just my first idea. We could figure something else out.
            #     pass
            # for path in center_element.getchildren():
            #     print(f"\t{path}")
            #     self.color_element(path, color)
            for elem in center_element:
                if elem.attrib["id"].startswith("Capital_Marker"):
                    continue
                if (f"{NAMESPACE['inkscape']}label" in elem.attrib
                      and elem.attrib[f"{NAMESPACE['inkscape']}label"] in ["Halfcore Marker", "Core Marker"]):
                    # Handling capitals is easy bc it's all marked
                    if elem.attrib[f"{NAMESPACE['inkscape']}label"] == "Halfcore Marker":
                        self._color_element(elem, half_color)
                    elif elem.attrib[f"{NAMESPACE['inkscape']}label"] == "Core Marker":
                        self._color_element(elem, core_color)
                elif half_color != core_color:
                    corename = "None" if not province.core else province.core.name
                    halfname = "None" if not province.half_core else province.half_core.name
                    self._color_element(elem, f"url(#{halfname}_{corename})")
                else:
                    self._color_element(elem, core_color)

    def _get_province_from_element_by_label(self, element: Element) -> Province:
        province_name = element.get(f"{NAMESPACE['inkscape']}label")
        if province_name is None:
            raise ValueError(f"Unlabeled element {element}")
        province = self.board.get_province(province_name)
        if province is None:
            raise ValueError(f"Could not find province for label {province_name}")
        return province

    def _draw_units(self) -> None:
        for unit in self.board.units:
            if unit.province.name in self.adjacent_provinces:
                self._draw_unit(unit)

    def _get_unit_coordinates(self,
                              unit: Unit,
                              province_coordinates: dict[UnitType | str, set[tuple[float, float]]]
                             ) -> set[tuple[float, float]]:
        if unit.coast:
            if unit.coast in province_coordinates:
                return province_coordinates[unit.coast]
        else:
            if unit.unit_type in province_coordinates:
                return province_coordinates[unit.unit_type]

        logger.warning(
            "Could not find coordinates for %s in province %s. Trying to find another coordinate to use",
            unit.unit_type,
            unit.province.name,
        )
        if len(province_coordinates) > 0:
            return next(iter(province_coordinates.values()))
        logger.warning("No coordinates found for province %s, using (0, 0) as fallback", unit.province.name)
        return {(0, 0)}

    def _draw_unit(self, unit: Unit, use_moves_svg=False):
        unit_element = self._get_element_for_unit_type(unit.unit_type)
        province = unit.province

        for path in unit_element:
            self._color_element(path, self.player_colors["Neutral" if unit.player is None else unit.player.name])

        current_coords = get_unit_coordinates(unit_element)
        current_coords = TransGL3(unit_element).transform(current_coords)

        province_coordinates = province.all_rets if unit == province.dislodged_unit else province.all_locs
        coord_list = self._get_unit_coordinates(unit, province_coordinates)

        for desired_coords in coord_list:
            elem = copy.deepcopy(unit_element)

            dx = desired_coords[0] - current_coords[0]
            dy = desired_coords[1] - current_coords[1]

            trans = TransGL3(elem) * TransGL3().init(x_c=dx, y_c=dy)

            elem.set("transform", str(trans))
            p = province.get_name(unit.coast)

            elem.set("onclick", f'obj_clicked(event, "{p}", true)')
            elem.set("oncontextmenu", f'obj_clicked(event, "{p}", true)')

            elem.set("id", province.name)
            elem.set("{http://www.inkscape.org/namespaces/inkscape}label", province.name)

            group = self.cached_elements["unit_output"] if not use_moves_svg else self._moves_svg.getroot()
            assert group is not None
            group.append(elem)

    def _highlight_retreating_units(self, svg):
        for unit in self.board.units:
            if unit == unit.province.dislodged_unit and unit.province.name in self.adjacent_provinces:
                self._draw_retreat_options(unit, svg)

    def _get_element_for_unit_type(self, unit_type) -> Element:
        # Just copy a random phantom unit
        if unit_type == UnitType.ARMY:
            layer: Element = self.cached_elements["army"]
        else:
            layer: Element = self.cached_elements["fleet"]
        return copy.deepcopy(layer[0])

    def _draw_retreat_options(self, unit: Unit, svg):
        root = svg.getroot()
        if not unit.retreat_options:
            self._draw_force_disband(unit.province.get_retreat_unit_coordinates(unit.unit_type, unit.coast), svg)
            return

        # TODO: Move into helper function along with logic in draw_moves_and_retreats
        unit_locs = unit.province.all_rets
        unit_locs = self._get_unit_coordinates(unit, unit_locs)

        for retreat_province, retreat_coast in unit.retreat_options:
            new_locs = []
            if unit.unit_type not in retreat_province.all_locs:
                e_list = next(iter(retreat_province.all_locs.values()))
            elif retreat_coast:
                e_list = retreat_province.all_locs[retreat_coast]
            else:
                e_list = retreat_province.all_locs[unit.unit_type]

            # Unspecified coast, so default to army location
            if isinstance(e_list, dict):
                e_list = retreat_province.all_locs[UnitType.ARMY]
            for endpoint in e_list:
                new_locs += [self._normalize(self.get_closest_loc(unit_locs, endpoint))]

            for loc in new_locs:
                root.append(
                    self._draw_retreat_move(
                        RetreatMove(retreat_province, retreat_coast), unit.unit_type, loc
                    )
                )

    def _initialize_scoreboard_locations(self) -> None:
        if not self.board_svg_data["power_banners"]:
            return
        all_power_banners_element = get_svg_element(
            self.board_svg, self.board_svg_data["power_banners"]
        )
        self.scoreboard_power_locations: list[tuple[float, float]] = []
        for power_element in all_power_banners_element or []:
            destination_pretransform_coordinates = (float(power_element[0].get("x", 0)),
                                                    float(power_element[0].get("y", 0)))
            destination_coordinates = TransGL3(power_element).transform(destination_pretransform_coordinates)
            self.scoreboard_power_locations.append(destination_coordinates)

        # each power is placed in the right spot based on the transform field which has value of
        # "translate($x,$y)" where x,y are floating point numbers; we parse these via regex and sort by y-value
        self.scoreboard_power_locations.sort(key=lambda loc: loc[1])

    def add_arrow_definition_to_svg(self, svg: ElementTree) -> None:
        """ Adds arrow marker definitions and half-core gradients to the SVG."""
        defs = svg.find("{http://www.w3.org/2000/svg}defs")
        if defs is None:
            defs = self._create_element("defs", {})
            root = svg.getroot()
            assert root is not None
            root.append(defs)
        # TODO: Check if 'arrow' id is already defined in defs
        arrow_marker: Element = self._create_element(
            "marker",
            {
                "id": "arrow",
                "viewbox": "0 0 3 3",
                "refX": "1.5",
                "refY": "1.5",
                "markerWidth": "3",
                "markerHeight": "3",
                "orient": "auto-start-reverse",
            },
        )
        arrow_path: Element = self._create_element(
            "path",
            {"d": "M 0,0 L 3,1.5 L 0,3 z"},
        )
        arrow_marker.append(arrow_path)
        defs.append(arrow_marker)
        red_arrow_marker: Element = self._create_element(
            "marker",
            {
                "id": "redarrow",
                "viewbox": "0 0 3 3",
                "refX": "1.5",
                "refY": "1.5",
                "markerWidth": "3",
                "markerHeight": "3",
                "orient": "auto-start-reverse",
            },
        )
        red_arrow_path: Element = self._create_element(
            "path",
            {"d": "M 0,0 L 3,1.5 L 0,3 z", "fill": "red"},
        )
        red_arrow_marker.append(red_arrow_path)
        defs.append(red_arrow_marker)

        ball_marker: Element = self._create_element(
            "marker",
            {
                "id": "ball",
                "viewbox": "0 0 3 3",
                # "refX": "1.5",
                # "refY": "1.5",
                "markerWidth": "3",
                "markerHeight": "3",
                "orient": "auto-start-reverse",
                "shape-rendering": "geometricPrecision", # Needed bc firefox is weird
                "overflow": "visible"
            },
        )
        ball_def: Element = self._create_element(
            "circle",
            {"r": "2", "fill": "black"},
        )
        ball_marker.append(ball_def)
        defs.append(ball_marker)

        red_ball_marker: Element = self._create_element(
            "marker",
            {
                "id": "redball",
                "viewbox": "0 0 3 3",
                # "refX": "1.5",
                # "refY": "1.5",
                "markerWidth": "3",
                "markerHeight": "3",
                "orient": "auto-start-reverse",
                "shape-rendering": "geometricPrecision", # Needed bc firefox is weird
                "overflow": "visible"
            },
        )
        red_ball_def: Element = self._create_element(
            "circle",
            {"r": "2", "fill": "red"},
        )
        red_ball_marker.append(red_ball_def)
        defs.append(red_ball_marker)

        if self.board.data.get("build_options") == "cores":
            created_defs = set()

            for province in self.board.provinces:
                if not province.has_supply_center or province.half_core is None:
                    continue
                mapping = (province.half_core.name, "None" if province.core is None else province.core.name)
                if mapping in created_defs:
                    continue

                created_defs.add(mapping)

                gradient_def: Element = self._create_element("linearGradient", {"id": f"{mapping[0]}_{mapping[1]}"})
                first: Element = self._create_element(
                    "stop", {"offset": "50%", "stop-color": f"#{self.player_colors[mapping[0]]}"}
                )
                second: Element = self._create_element(
                    "stop", {"offset": "50%", "stop-color": f"#{self.player_colors[mapping[1]]}"}
                )
                gradient_def.append(first)
                gradient_def.append(second)
                defs.append(gradient_def)

    def _color_element(self, element: Element, color: str, key="fill"):
        if len(color) == 6:  # Potentially buggy hack; just assume everything with length 6 is rgb without #
            color = f"#{color}"
        if element.get(key) is not None:
            element.set(key, color)
        if element.get("style") is not None and key in (element.get("style") or ""):
            style = element.get("style")
            assert style is not None
            style = re.sub(key + r":#[0-9a-fA-F]{6}", f"{key}:{color}", style)
            element.set("style", style)

    def _create_element(self, tag: str, attributes: dict[str, any]) -> etree.Element:
        attributes_str = {key: str(val) for key, val in attributes.items()}
        return etree.Element(tag, attributes_str)

    # returns equivalent point within the map
    def _normalize(self, point: tuple[float, float]):
        return (point[0] % self.board_svg_data["map_width"], point[1])

    # returns closest point in a set
    # will wrap horizontally
    def get_closest_loc(self,
                        possibilities: set[tuple[float, float]],
                        coord: tuple[float, float]) -> tuple[float, float]:
        """Gets the closest point to the given coordinate, accounting for horizontal wrapping of the map."""
        possibilities_list = list(possibilities)
        crossed_pos = []
        crossed = []
        for p in possibilities_list:
            x = p[0]
            cx = coord[0]
            if abs(x - cx) > self.board_svg_data["map_width"] / 2:
                crossed += [1]
                if x > cx:
                    x -= self.board_svg_data["map_width"]
                else:
                    x += self.board_svg_data["map_width"]
            else:
                crossed += [0]
            crossed_pos += [(x, p[1])]

        crossed = np.array(crossed)
        crossed_pos = np.array(crossed_pos)

        dists = crossed_pos - coord
        # penalty for crossing map is 500 px
        short_ind = np.argmin(np.linalg.norm(dists, axis=1) + 500 * crossed)
        return crossed_pos[short_ind].tolist()

    def _loc_to_point(self, loc: Province, unit_type: UnitType, coast: str | None,
                     current: tuple[float, float], use_retreats=False) -> tuple[float, float]:
        # If we're moving to somewhere that's inhabitted, draw to the proper coast
        if loc.unit:
            unit_type = loc.unit.unit_type
            coast = loc.unit.coast

        coord_list = loc.all_rets if use_retreats else loc.all_locs
        if coast and coast in coord_list:
            coords = coord_list[coast]
        elif unit_type in coord_list:
            coords = coord_list[unit_type]
        else:
            coords = next(iter(coord_list.values()))

        return self.get_closest_loc(coords, current)

    def pull_coordinate(
        self, anchor: tuple[float, float], coordinate: tuple[float, float], pull=None, limit=0.25
    ) -> tuple[float, float]:
        """
        Pull coordinate toward anchor by a small margin to give unit view breathing room. The pull will be limited to be
        no more than the given percent of the distance because otherwise small province size areas are hard to see.
        """
        if pull is None:
            pull = 1.5 * self.board_svg_data["unit_radius"]

        ax, ay = anchor
        cx, cy = coordinate
        dx = ax - cx
        dy = ay - cy

        distance = math.sqrt(dx**2 + dy**2)
        if distance == 0:
            return coordinate

        # if the area is small, the pull can become too large of the percent of the total arrow length
        pull = min(pull, distance * limit)

        scale = pull / distance
        return cx + dx * scale, cy + dy * scale
