import unittest

from DiploGM.models.unit import UnitType
from test.utils import BoardBuilder

class TestTransform(unittest.TestCase):
    def test_transform_1(self):
        """ 
            Transforming should fail for non-SCs.
            Germany: A Prussia Transforms
            Prussia shouldn't be a fleet.
        """
        b = BoardBuilder()
        a_prussia = b.transform(b.players["Germany"], UnitType.ARMY, "Prussia")

        b.assert_illegal(a_prussia)
        b.moves_adjudicate(self)
        self.assertNotEqual(a_prussia.unit_type, UnitType.FLEET, "Prussia shouldn't be a fleet")

    def test_transform_2(self):
        """ 
            Transforming should fail for not owned provinces.
            Germany doesn't own Holland.
            Germany: F Holland Transforms
            Holland shouldn't be an army.
        """
        b = BoardBuilder()
        f_holland = b.transform(b.players["Germany"], UnitType.FLEET, "Holland")

        b.assert_illegal(f_holland)
        b.moves_adjudicate(self)
        self.assertNotEqual(f_holland.unit_type, UnitType.ARMY, "Holland shouldn't be an army")

    def test_transform_3(self):
        """ 
            Transforming should turn armies into fleets.
            Germany owns Kiel.
            Germany: A Kiel Transforms
            Kiel should be a fleet.
        """
        b = BoardBuilder()
        a_kiel = b.transform(b.players["Germany"], UnitType.ARMY, "Kiel")

        b.assert_success(a_kiel)
        b.moves_adjudicate(self)
        self.assertEqual(a_kiel.unit_type, UnitType.FLEET, "Kiel should be a fleet")

    def test_transform_4(self):
        """ 
            Transforming should turn fleets into armies.
            Germany owns Kiel.
            Germany: F Kiel Transforms
            Kiel should be an army.
        """
        b = BoardBuilder()
        f_kiel = b.transform(b.players["Germany"], UnitType.FLEET, "Kiel")

        b.assert_success(f_kiel)
        b.moves_adjudicate(self)
        self.assertEqual(f_kiel.unit_type, UnitType.ARMY, "Kiel should be an army")

    def test_transform_5(self):
        """ 
            Transforming should fail in an inland province.
            Germany owns Munich.
            Germany: A Munich Transforms
            Munich shouldn't be a fleet.
        """
        b = BoardBuilder()
        a_munich = b.transform(b.players["Germany"], UnitType.ARMY, "Munich")

        b.assert_illegal(a_munich)
        b.moves_adjudicate(self)
        self.assertNotEqual(a_munich.unit_type, UnitType.FLEET, "Munich shouldn't be a fleet")

    def test_transform_6(self):
        """ 
            Transforming should fail when the unit is attacked.
            Germany owns Holland.
            Germany: A Holland Transforms
            France: A Belgium - Holland
            Holland shouldn't be a fleet.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        a_holland = b.transform(b.players["Germany"], UnitType.ARMY, "Holland")
        a_belgium = b.move(b.players["France"], UnitType.ARMY, "Belgium", "Holland")

        b.assert_fail(a_holland, a_belgium)
        b.assert_not_illegal(a_holland, a_belgium)
        b.moves_adjudicate(self)

        self.assertNotEqual(a_holland.unit_type, UnitType.FLEET, "Holland shouldn't be a fleet")

    def test_transform_7(self):
        """ 
            Transforming should fail when the attacking unit is of the same nationality.
            Germany owns Holland.
            Germany: F Holland Transforms
            Germany: A Belgium - Holland
            Holland shouldn't be an army.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        f_holland = b.transform(b.players["Germany"], UnitType.FLEET, "Holland")
        a_belgium = b.move(b.players["Germany"], UnitType.ARMY, "Belgium", "Holland")

        b.assert_fail(f_holland, a_belgium)
        b.assert_not_illegal(f_holland, a_belgium)
        b.moves_adjudicate(self)

        self.assertNotEqual(f_holland.unit_type, UnitType.ARMY, "Holland shouldn't be an army")

    def test_transform_8(self):
        """ 
            Transforming should fail when attacked by convoy.
            Germany owns Holland.
            Germany: A Holland Transforms
            England: A London - Holland
            England: F North Sea Convoys A London - Holland
            Holland should be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        a_holland = b.transform(b.players["Germany"], UnitType.ARMY, "Holland")
        a_london = b.move(b.players["England"], UnitType.ARMY, "London", "Holland")
        f_north_sea = b.convoy(b.players["England"], "North Sea", a_london, "Holland")

        b.assert_fail(a_holland, a_london)
        b.assert_not_illegal(a_holland, f_north_sea, a_london)
        b.moves_adjudicate(self)

        self.assertNotEqual(a_holland.unit_type, UnitType.FLEET, "Holland shouldn't be a fleet")

    def test_transform_9(self):
        """ 
            Transforming should fail when attacked by convoy of the same nationality.
            Germany owns Holland.
            Germany: F Holland Transforms
            Germany: A London - Holland
            England: F North Sea Convoys A London - Holland
            Holland should be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        f_holland = b.transform(b.players["Germany"], UnitType.FLEET, "Holland")
        a_london = b.move(b.players["Germany"], UnitType.ARMY, "London", "Holland")
        f_north_sea = b.convoy(b.players["England"], "North Sea", a_london, "Holland")

        b.assert_fail(f_holland, a_london)
        b.assert_not_illegal(f_holland, f_north_sea, a_london)
        b.moves_adjudicate(self)

        self.assertNotEqual(f_holland.unit_type, UnitType.ARMY, "Holland shouldn't be an army")

    def test_transform_10(self):
        """ 
            Transforming should succeed when only attacked by a disrupted convoy.
            Germany owns Holland.
            Germany: F Holland Transforms
            England: A London - Holland
            Holland should be half-cored by Germany.
        """
        b = BoardBuilder()
        p_holland = b.board.get_province("Holland")
        p_holland.owner = b.players["Germany"]
        f_holland = b.transform(b.players["Germany"], UnitType.FLEET, "Holland")
        _ = b.move(b.players["England"], UnitType.ARMY, "London", "Holland")

        b.assert_success(f_holland)
        b.moves_adjudicate(self)

        self.assertEqual(f_holland.unit_type, UnitType.ARMY, "Holland should be an army")

    def test_transform_11(self):
        """
            Transforming should succeed when done by a fleet in a province with multiple coasts.
            Russia owns St. Petersburg
            Russia: F St. Petersburg (sc) Transforms
            St. Petersburg should be an army.
        """
        b = BoardBuilder()
        f_st_petersburg = b.transform(b.players["Russia"], UnitType.FLEET, "St. Petersburg sc")
        b.assert_success(f_st_petersburg)
        b.moves_adjudicate(self)    
        self.assertEqual(f_st_petersburg.unit_type, UnitType.ARMY, "St. Petersburg should be an army")

    def test_transform_12(self):
        """
            Transforming should succeed when done by a army in a province with multiple coasts and a coast specified.
            Russia owns St. Petersburg
            Russia: A St. Petersburg Transforms sc
            St. Petersburg should be an fleet on the south coast.
        """
        b = BoardBuilder()
        a_st_petersburg = b.transform(b.players["Russia"], UnitType.ARMY, "St. Petersburg", "sc")
        b.assert_success(a_st_petersburg)
        b.moves_adjudicate(self)    
        self.assertEqual(a_st_petersburg.unit_type, UnitType.FLEET, "St. Petersburg should be a fleet")
        self.assertEqual(a_st_petersburg.coast, "sc", "F St. Petersburg should be on the south coast")

    def test_transform_13(self):
        """
            Transforming should fail when done by a army in a province with multiple coasts and no coast specified.
            Russia owns St. Petersburg
            Russia: A St. Petersburg Transforms
            St. Petersburg shouldn't be a fleet.
        """
        b = BoardBuilder()
        a_st_petersburg = b.transform(b.players["Russia"], UnitType.ARMY, "St. Petersburg")
        b.assert_illegal(a_st_petersburg)
        b.moves_adjudicate(self)    
        self.assertEqual(a_st_petersburg.unit_type, UnitType.ARMY, "St. Petersburg shouldn't be a fleet")