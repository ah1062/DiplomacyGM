import unittest

from DiploGM.models.unit import UnitType
from test.utils import BoardBuilder

class TestCore(unittest.TestCase):
    def test_core_1(self):
        """ 
            Coring should fail for non-SCs.
            Germany: A Silesia Cores
            Silesia shouldn't be half-cored by Germany.
        """
        b = BoardBuilder()
        a_silesia = b.core(b.players["Germany"], UnitType.ARMY, "Silesia")
        p_silesia = b.board.get_province("Silesia")

        b.assert_illegal(a_silesia)
        b.moves_adjudicate(self)
        self.assertNotEqual(p_silesia.core_data.half_core, b.players["Germany"], "Silesia shouldn't be cored")

    def test_core_2(self):
        """ 
            Coring should fail for not owned provinces.
            Germany doesn't own Holland.
            Germany: A Holland Cores
            Holland shouldn't be half-cored by Germany.
        """
        b = BoardBuilder()
        a_holland = b.core(b.players["Germany"], UnitType.ARMY, "Holland")
        p_holland = b.board.get_province("Holland")

        b.assert_illegal(a_holland)
        b.moves_adjudicate(self)
        self.assertNotEqual(p_holland.core_data.half_core, b.players["Germany"], "Holland shouldn't be cored")

    def test_core_3(self):
        """ 
            Coring should turn empty cores into half cores.
            Germany owns Holland.
            Germany: A Holland Cores
            Holland should be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        a_holland = b.core(b.players["Germany"], UnitType.ARMY, "Holland")

        b.assert_success(a_holland)
        b.moves_adjudicate(self)
        self.assertEqual(p_holland.core_data.half_core, b.players["Germany"], "Holland should be half-cored")

    def test_core_4(self):
        """ 
            Coring should turn half cores into full cores.
            Germany owns Holland.
            Germany: A Holland Cores
            Holland should be cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        p_holland.core_data.half_core = b.players["Germany"]
        a_holland = b.core(b.players["Germany"], UnitType.ARMY, "Holland")

        b.assert_success(a_holland)
        b.moves_adjudicate(self)
        self.assertEqual(p_holland.core_data.core, b.players["Germany"], "Holland should be cored")

    def test_core_5(self):
        """ 
            Coring should fail when the coring unit is attacked.
            Germany owns Holland.
            Germany: A Holland Cores
            France: A Belgium - Holland
            Holland shouldn't be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        p_holland.core_data.half_core = b.players["Germany"]
        a_holland = b.core(b.players["Germany"], UnitType.ARMY, "Holland")
        a_belgium = b.move(b.players["France"], UnitType.ARMY, "Belgium", "Holland")

        b.assert_fail(a_holland, a_belgium)
        b.assert_not_illegal(a_holland, a_belgium)
        b.moves_adjudicate(self)

        self.assertNotEqual(p_holland.core_data.core, b.players["Germany"], "Holland shouldn't be cored")

    def test_core_6(self):
        """ 
            Coring should fail when the attacking unit is of the same nationality.
            Germany owns Holland.
            Germany: A Holland Cores
            Germany: A Belgium - Holland
            Holland shouldn't be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        p_holland.core_data.half_core = b.players["Germany"]
        a_holland = b.core(b.players["Germany"], UnitType.ARMY, "Holland")
        a_belgium = b.move(b.players["Germany"], UnitType.ARMY, "Belgium", "Holland")

        b.assert_fail(a_holland, a_belgium)
        b.assert_not_illegal(a_holland, a_belgium)
        b.moves_adjudicate(self)

        self.assertNotEqual(p_holland.core_data.core, b.players["Germany"], "Holland shouldn't be cored")

    def test_core_7(self):
        """ 
            Coring should fail when attacked by convoy.
            Germany owns Holland.
            Germany: A Holland Cores
            England: A London - Holland
            England: F North Sea Convoys A London - Holland
            Holland should be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        p_holland.core_data.half_core = b.players["Germany"]
        a_holland = b.core(b.players["Germany"], UnitType.ARMY, "Holland")
        a_london = b.move(b.players["England"], UnitType.ARMY, "London", "Holland")
        f_north_sea = b.convoy(b.players["England"], "North Sea", a_london, "Holland")

        b.assert_fail(a_holland, a_london)
        b.assert_not_illegal(a_holland, f_north_sea, a_london)
        b.moves_adjudicate(self)

        self.assertNotEqual(p_holland.core_data.core, b.players["Germany"], "Holland shouldn't be cored")

    def test_core_8(self):
        """ 
            Coring should fail when attacked by convoy of the same nationality.
            Germany owns Holland.
            Germany: A Holland Cores
            Germany: A London - Holland
            England: F North Sea Convoys A London - Holland
            Holland should be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        p_holland.core_data.half_core = b.players["Germany"]
        a_holland = b.core(b.players["Germany"], UnitType.ARMY, "Holland")
        a_london = b.move(b.players["Germany"], UnitType.ARMY, "London", "Holland")
        f_north_sea = b.convoy(b.players["England"], "North Sea", a_london, "Holland")

        b.assert_fail(a_holland, a_london)
        b.assert_not_illegal(a_holland, f_north_sea, a_london)
        b.moves_adjudicate(self)

        self.assertNotEqual(p_holland.core_data.core, b.players["Germany"], "Holland shouldn't be cored")


    def test_core_9(self):
        """ 
            Coring should succeed when only attacked by a disrupted convoy.
            Germany owns Holland.
            Germany: A Holland Cores
            England: A London - Holland
            Holland should be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        p_holland.core_data.half_core = b.players["Germany"]
        a_holland = b.core(b.players["Germany"], UnitType.ARMY, "Holland")
        b.move(b.players["England"], UnitType.ARMY, "London", "Holland")

        b.assert_success(a_holland)
        b.moves_adjudicate(self)

        self.assertEqual(p_holland.core_data.core, b.players["Germany"], "Holland should be cored")
