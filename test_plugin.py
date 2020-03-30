import unittest

from plugin import Command, TextCommand

class TestCommand(unittest.TestCase):
    def test_cannot_instatiate(self):
        """You should not be able to instatiate the abstract class.
        """
        with self.assertRaises(TypeError):
            Command()

class TestTextCommand(unittest.TestCase):
    def test_cannot_instatiate(self):
        """You should not be able to instatiate the abstract class.
        """
        with self.assertRaises(TypeError):
            TextCommand()

if __name__ == '__main__':
    unittest.main()