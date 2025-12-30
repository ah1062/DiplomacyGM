import unittest

from DiploGM.models.unit import UnitType
from DiploGM.parse_order import parse_order
from test.utils import BoardBuilder

# These tests are based off https://webdiplomacy.net/doc/DATC_v3_0.html, with 
# https://github.com/diplomacy/diplomacy/blob/master/diplomacy/tests/test_datc.py being used as a reference as well.

# 6.B. TEST CASES, COASTAL ISSUES
class TestDATC_B(unittest.TestCase):
    def test_6_b_1(self):
        """ 6.B.1. TEST CASE, MOVING WITH UNSPECIFIED COAST WHEN COAST IS NECESSARY
            Coast is significant in this case:
            France: 
            F Portugal - Spain
            Move should fail.
        """
        b = BoardBuilder()
        f_portugal = b.move(b.france, UnitType.FLEET, "Portugal", "Spain")

        b.assertFail(f_portugal)
        b.moves_adjudicate(self)

    def test_6_b_2(self):
        """ 6.B.2. TEST CASE, MOVING WITH UNSPECIFIED COAST WHEN COAST IS NOT NECESSARY
            There is only one coast possible in this case:
            France: 
            F Gascony - Spain
            Since the North Coast is the only coast that can be reached, it seems logical that a move is attempted to the north coast of Spain. See issue 4.B.2.
            I prefer that an attempt is made to the only possible coast, the north coast of Spain.
        """
        b = BoardBuilder()
        f_gascony = b.move(b.france, UnitType.FLEET, "Gascony", "Spain")

        b.assertSuccess(f_gascony)
        b.moves_adjudicate(self)

    def test_6_b_3(self):
        """ 6.B.3. TEST CASE, MOVING WITH WRONG COAST WHEN COAST IS NOT NECESSARY
            If only one coast is possible, but the wrong coast can be specified.
            France: F Gascony - Spain(sc)
            If the rules are played very clemently, a move will be attempted to the north coast of Spain.
            However, since this order is very clear and precise, it is more common that the move fails (see 4.B.3).
            I prefer that the move fails.
        """
        b = BoardBuilder()
        f_gascony = b.move(b.france, UnitType.FLEET, "Gascony", "Spain sc")

        b.assertFail(f_gascony)
        b.moves_adjudicate(self)

    def test_6_b_4(self):
        """ 6.B.4. TEST CASE, SUPPORT TO UNREACHABLE COAST ALLOWED
            A fleet can give support to a coast where it can not go.
            France: F Gascony - Spain(nc)
            France: F Marseilles Supports F Gascony - Spain(nc)
            Italy: F Western Mediterranean - Spain(sc)
            Although the fleet in Marseilles can not go to the north coast it can still
            support targeting the north coast. So, the support is successful, the move of the fleet
            in Gasgony succeeds and the move of the Italian fleet fails.
        """
        b = BoardBuilder()
        f_gascony = b.move(b.france, UnitType.FLEET, "Gascony", "Spain nc")
        f_marseilles = b.supportMove(b.france, UnitType.FLEET, "Marseilles", f_gascony, "Spain nc")
        f_western_mediterranean = b.move(b.italy, UnitType.FLEET, "Western Mediterranean Sea", "Spain sc")

        b.assertSuccess(f_gascony)
        b.assertSuccess(f_marseilles)
        b.assertFail(f_western_mediterranean)
        b.moves_adjudicate(self)

    def test_6_b_5(self):
        """ 6.B.5. TEST CASE, SUPPORT FROM UNREACHABLE COAST NOT ALLOWED
            A fleet can not give support to an area that can not be reached from the current coast of the fleet.
            France: F Marseilles - Gulf of Lyon
            France: F Spain(nc) Supports F Marseilles - Gulf of Lyon
            Italy: F Gulf of Lyon Hold
            The Gulf of Lyon can not be reached from the North Coast of Spain. Therefore, the support of
            Spain is invalid and the fleet in the Gulf of Lyon is not dislodged.
        """
        b = BoardBuilder()
        f_marseilles = b.move(b.france, UnitType.FLEET, "Marseilles", "Gulf of Lyon")
        f_spain_nc = b.supportMove(b.france, UnitType.FLEET, "Spain nc", f_marseilles, "Gulf of Lyon")
        b.hold(b.italy, UnitType.FLEET, "Gulf of Lyon")

        b.assertIllegal(f_spain_nc)
        b.assertFail(f_marseilles)
        b.moves_adjudicate(self)
    
    def test_6_b_6(self):
        """ 6.B.6. TEST CASE, SUPPORT CAN BE CUT WITH OTHER COAST
            Support can be cut from the other coast.
            England: F Irish Sea Supports F North Atlantic Ocean - Mid-Atlantic Ocean
            England: F North Atlantic Ocean - Mid-Atlantic Ocean
            France: F Spain(nc) Supports F Mid-Atlantic Ocean
            France: F Mid-Atlantic Ocean Hold
            Italy: F Gulf of Lyon - Spain(sc)
            The Italian fleet in the Gulf of Lyon will cut the support in Spain. That means
            that the French fleet in the Mid Atlantic Ocean will be dislodged by the English fleet
            in the North Atlantic Ocean.
        """
        b = BoardBuilder()
        f_north_atlantic_ocean = b.move(b.england, UnitType.FLEET, "North Atlantic Ocean", "Mid-Atlantic Ocean")
        b.supportMove(b.england, UnitType.FLEET, "Irish Sea", f_north_atlantic_ocean, "Mid-Atlantic Ocean")
        f_mid_atlantic_ocean = b.hold(b.france, UnitType.FLEET, "Mid-Atlantic Ocean")
        f_spain_nc = b.supportHold(b.france, UnitType.FLEET, "Spain nc", f_mid_atlantic_ocean)
        f_gulf_of_lyon = b.move(b.italy, UnitType.FLEET, "Gulf of Lyon", "Spain sc")

        b.assertFail(f_gulf_of_lyon)
        b.assertFail(f_spain_nc)
        b.assertSuccess(f_north_atlantic_ocean)
        b.assertDislodge(f_mid_atlantic_ocean)
        b.moves_adjudicate(self)

    def test_6_b_7(self):
        """6.B.7. TEST CASE, SUPPORTING OWN UNIT WITH UNSPECIFIED COAST
            It is a little bit harsh to reject this.
            France:
            F Portugal Supports F Mid-Atlantic Ocean - Spain given
            F Mid-Atlantic Ocean - Spain(nc) fails

            Italy:
            F Gulf of Lyon Supports F Western Mediterranean - Spain(sc) given
            F Western Mediterranean - Spain(sc) fails

            See issue 4.B.4.

            I prefer that the support succeeds and the Italian fleet in the Western Mediterranean bounces.
            However, if orders are checked on submission (such as in web-based play), support without
            coast should not be given as an option.
        """
        b = BoardBuilder()
        f_mid_atlantic_ocean = b.move(b.france, UnitType.FLEET, "Mid-Atlantic Ocean", "Spain nc")
        f_portugal = b.supportMove(b.france, UnitType.FLEET, "Portugal", f_mid_atlantic_ocean, "Spain")
        f_western_mediterranean = b.move(b.italy, UnitType.FLEET, "Western Mediterranean", "Spain sc")
        b.supportMove(b.italy, UnitType.FLEET, "Gulf of Lyon", f_western_mediterranean, "Spain sc")

        b.assertNotIllegal(f_portugal)
        b.assertFail(f_mid_atlantic_ocean, f_western_mediterranean)
        b.moves_adjudicate(self)

    def test_6_b_8(self):
        """6.B.8. TEST CASE, SUPPORTING WITH UNSPECIFIED COAST WHEN ONLY ONE COAST IS POSSIBLE
            If coast is omitted while only coast is possible, it should be considered a poorly
            written order, that should be followed.
            France:
            F Portugal Supports F Gascony - Spain given
            F Gascony - Spain(nc) fails

            Italy:
            F Gulf of Lyon Supports F Western Mediterranean - Spain(sc) given
            F Western Mediterranean - Spain(sc) fails

            Support of Portugal is successful.
        """
        b = BoardBuilder()
        f_gascony = b.move(b.france, UnitType.FLEET, "Gascony", "Spain nc")
        f_portugal = b.supportMove(b.france, UnitType.FLEET, "Portugal", f_gascony, "Spain")
        f_western_mediterranean = b.move(b.italy, UnitType.FLEET, "Western Mediterranean", "Spain sc")
        b.supportMove(b.italy, UnitType.FLEET, "Gulf of Lyon", f_western_mediterranean, "Spain sc")

        b.assertNotIllegal(f_portugal)
        b.assertFail(f_gascony, f_western_mediterranean)
        b.moves_adjudicate(self)

    def test_6_b_9(self):
        """6.B.9. TEST CASE, SUPPORTING WITH WRONG COAST
            It should be possible to specify a coast and that coast should match.
            France:
            F Portugal Supports F Mid-Atlantic Ocean - Spain(nc) invalid
            F Mid-Atlantic Ocean - Spain(sc) fails

            Italy:
            F Gulf of Lyon Supports F Western Mediterranean - Spain(sc) given
            F Western Mediterranean - Spain(sc) succeeds

            See issue 4.B.4. Coastal specification in Portugal support order does not match, making it invalid.
        """
        b = BoardBuilder()
        f_mid_atlantic_ocean = b.move(b.france, UnitType.FLEET, "Mid-Atlantic Ocean", "Spain nc")
        f_portugal = b.supportMove(b.france, UnitType.FLEET, "Portugal", f_mid_atlantic_ocean, "Spain sc")
        f_western_mediterranean = b.move(b.italy, UnitType.FLEET, "Western Mediterranean", "Spain sc")
        b.supportMove(b.italy, UnitType.FLEET, "Gulf of Lyon", f_western_mediterranean, "Spain sc")

        b.assertIllegal(f_portugal)
        b.assertFail(f_mid_atlantic_ocean)
        b.assertSuccess(f_western_mediterranean)
        b.moves_adjudicate(self)

    def test_6_b_10(self):
        """6.B.10. TEST CASE, UNIT ORDERED WITH WRONG COAST
            A player might specify the wrong coast for the ordered unit.
            France owns F Spain(sc)

            France:
            F Spain(nc) - Gulf of Lyon succeeds

            If only perfect orders are accepted, then the move will fail, but since the
            coast for the ordered unit has no purpose, it might also be ignored (see issue 4.B.5).

            I prefer that a move will be attempted.
        """
        b = BoardBuilder()
        f_spain = b.fleet("Spain sc", b.france)
        parse_order(".order Spain nc - Gulf of Lyon", None, b.board)

        b.assertNotIllegal(f_spain)
        b.assertSuccess(f_spain)
        b.moves_adjudicate(self)

    def test_6_b_11(self):
        """6.B.11. TEST CASE, COAST CANNOT BE ORDERED TO CHANGE
            The coast cannot change by just ordering the other coast.
            France owns F Spain(nc)

            France:
            F Spain(sc) - Gulf of Lyon fails
        """
        b = BoardBuilder()
        f_spain = b.fleet("Spain nc", b.france)
        parse_order(".order Spain sc - Gulf of Lyon", None, b.board)

        b.assertIllegal(f_spain)
        b.moves_adjudicate(self)

    def test_6_b_12(self):
        """For armies the coasts are irrelevant:
            France:
            A Gascony - Spain(nc) succeeds

            If only perfect orders are accepted, then the move will fail. But it is also possible
            that coasts are ignored in this case and a move will be attempted (see issue 4.B.6).

            I prefer that a move will be attempted.
        """
        b = BoardBuilder()
        a_gascony = b.move(b.france, UnitType.ARMY, "Gascony", "Spain nc")

        b.assertNotIllegal(a_gascony)
        b.assertSuccess(a_gascony)
        b.moves_adjudicate(self)

    def test_6_b_13(self):
        """ 6.B.13. TEST CASE, COASTAL CRAWL NOT ALLOWED
            If a fleet is leaving a sector from a certain coast while in the opposite direction another fleet
            is moving to another coast of the sector, it is still a head to head battle. This has been decided in
            the great revision of the 1961 rules that resulted in the 1971 rules.
            Turkey: F Bulgaria(sc) - Constantinople
            Turkey: F Constantinople - Bulgaria(ec)
            Both moves fail.
        """
        b = BoardBuilder()
        f_bulgaria_sc = b.move(b.turkey, UnitType.FLEET, "Bulgaria sc", "Constantinople")
        f_constantinople = b.move(b.turkey, UnitType.FLEET, "Constantinople", "Bulgaria ec")
        
        b.assertFail(f_bulgaria_sc)
        b.assertFail(f_constantinople)
        b.moves_adjudicate(self)

    def test_6_b_14(self):
        """ 6.B.14. TEST CASE, BUILDING WITH UNSPECIFIED COAST
            Coast must be specified in certain build cases:
            Russia owns SC St Petersburg

            Russia:
            Build F St Petersburg fails

            See issue 4.B.7. Build fails, subsequent build orders may use up this right to build.
        """
        b = BoardBuilder()
        b.build(b.russia, (UnitType.FLEET, "St. Petersburg"))
        b.assertBuildCount(0)
        b.builds_adjudicate(self)

    def test_6_b_15(self):
        """ 6.B.15. TEST CASE, SUPPORTING FOREIGN UNIT WITH UNSPECIFIED COAST
            Opinions differ on this.
            France:
            F Portugal Supports F Mid-Atlantic Ocean - Spain given

            England:
            F Mid-Atlantic Ocean - Spain(nc) fails

            Italy:
            F Gulf of Lyon Supports F Western Mediterranean - Spain(sc) given
            F Western Mediterranean - Spain(sc) fails

            See issue 4.B.4.

            Although the move to the north coast of Spain might be a surprise for France, it is hard to believe
            that England somehow tricked France. Therefore, I prefer that the support succeeds and the Italian fleet
            in the Western Mediterranean bounces. However, if orders are checked on submission (such as in web-based
            play), support without coast should not be given as an option.
        """
        b = BoardBuilder()
        f_mid_atlantic_ocean = b.move(b.england, UnitType.FLEET, "Mid-Atlantic Ocean", "Spain nc")
        f_portugal = b.supportMove(b.france, UnitType.FLEET, "Portugal", f_mid_atlantic_ocean, "Spain")
        f_western_mediterranean = b.move(b.italy, UnitType.FLEET, "Western Mediterranean", "Spain sc")
        b.supportMove(b.italy, UnitType.FLEET, "Gulf of Lyon", f_western_mediterranean, "Spain sc")

        b.assertNotIllegal(f_portugal)
        b.assertFail(f_mid_atlantic_ocean, f_western_mediterranean)
        b.moves_adjudicate(self)

    def test_6_b_16(self):
        """ 6.B.16. TEST CASE, HOLD SUPPORT WITH WRONG COAST
            For a fleet holding on a multi-coast province, the coast doesn't need to be agreed on.
            France:
            A Gascony - Spain fails
            A Marseilles Supports A Gascony - Spain given

            Italy:
            F Spain(sc) Holds stands

            England:
            F Portugal Supports F Spain(nc) given

            See issue 4.B.5.

            Although the English support order contains the wrong coast, the coast specification
            is not required. Therefore, I prefer that the support is valid.
        """
        b = BoardBuilder()
        a_gascony = b.move(b.france, UnitType.ARMY, "Gascony", "Spain")
        b.supportMove(b.france, UnitType.ARMY, "Marseilles", a_gascony, "Spain")
        f_spain = b.hold(b.italy, UnitType.FLEET, "Spain sc")
        f_portugal = b.fleet("Portugal", b.england)
        parse_order(".order Portugal s Spain nc", None, b.board)

        b.assertNotIllegal(f_portugal)
        b.assertFail(a_gascony)
        b.assertNotDislodge(f_spain)
        b.moves_adjudicate(self)

    def test_6_b_17(self):
        """ 6.B.17. TEST CASE, MOVE SUPPORT WITH WRONG COAST FOR DEPARTURE PROVINCE
            For a fleet moving from a multi-coast province, the coast doesn't need to be agreed on.
            England:
            F Mid-Atlantic Ocean Holds dislodged

            France:
            F Spain(sc) - Mid-Atlantic Ocean succeeds

            Italy:
            F Western Mediterranean Supports F Spain(nc) - Mid-Atlantic Ocean given

            See issue 4.B.5.

            Also, for a move support the coast specification of the departing province is not
            required. Therefore, I prefer that the support is valid.
        """
        b = BoardBuilder()
        f_mid_atlantic_ocean = b.hold(b.england, UnitType.FLEET, "Mid-Atlantic Ocean")
        f_spain = b.move(b.france, UnitType.FLEET, "Spain sc", "Mid-Atlantic Ocean")
        f_western_mediterranean = b.fleet("Western Mediterranean Sea", b.italy)
        parse_order(".order Western Mediterranean Sea s Spain nc - Mid-Atlantic Ocean", None, b.board)

        b.assertNotIllegal(f_western_mediterranean)
        b.assertSuccess(f_spain)
        b.assertDislodge(f_mid_atlantic_ocean)
        b.moves_adjudicate(self)

    def test_6_b_18(self):
        """ 6.B.18. TEST CASE, CONVOY STARTING FROM MULTI-COAST PROVINCE
            A convoy follows fleet movement. However, if starting at a multi-coast province,
            the army position (without coast specification) is not a legal fleet position.
            Turkey:
            A Bulgaria - Sevastopol succeeds
            F Black Sea Convoys A Bulgaria - Sevastopol available
        """
        b = BoardBuilder()
        a_bulgaria = b.move(b.turkey, UnitType.ARMY, "Bulgaria", "Sevastopol")
        f_black_sea = b.convoy(b.turkey, "Black Sea", a_bulgaria, "Sevastopol")

        b.assertNotIllegal(f_black_sea)
        b.assertSuccess(a_bulgaria)
        b.moves_adjudicate(self)

    def test_6_b_19(self):
        """ 6.B.19. TEST CASE, CONVOY ENDING AT MULTI-COAST PROVINCE
            Similar to the previous test case, but now the convoy is ending at a multi-coast province.
            Italy:
            A Tuscany - Spain succeeds
            F Gulf of Lyon Convoys A Tuscany - Spain available
        """
        b = BoardBuilder()
        a_tuscany = b.move(b.italy, UnitType.ARMY, "Tuscany", "Spain")
        f_gulf_of_lyon = b.convoy(b.italy, "Gulf of Lyon", a_tuscany, "Spain")

        b.assertNotIllegal(f_gulf_of_lyon)
        b.assertSuccess(a_tuscany)
        b.moves_adjudicate(self)