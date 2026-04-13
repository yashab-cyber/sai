import unittest
from unittest.mock import MagicMock
from modules.planner import Planner
from core.brain import Brain

class TestPlanner(unittest.TestCase):

    def setUp(self):
        mock_brain = MagicMock(spec=Brain)
        self.planner = Planner(brain=mock_brain)
        self.mock_brain = mock_brain

    def test_determine_next_step(self):
        task = 'Sample Task'
        history = [{'action': 'action1', 'observation': 'obs1'}, {'action': 'action2', 'observation': 'obs2'}]

        # Mock the brain response
        self.mock_brain.prompt.return_value = {'next_step': 'do_something'}

        result = self.planner.determine_next_step(task, history)
        
        # Verify result
        self.assertEqual(result['next_step'], 'do_something')
        
        # Verify brain prompt was called (we don't check exact string due to complexity, but we check count)
        self.assertEqual(self.mock_brain.prompt.call_count, 1)

    def test_generate_subtasks(self):
        task = 'Complex Task'

        # Mock the brain response
        self.mock_brain.prompt.return_value = {'subtasks': ['Task 1', 'Task 2']}

        result = self.planner.generate_subtasks(task)

        self.mock_brain.prompt.assert_called_once_with(
            'decompose_task', f"Task: {task}\n\nDecompose this task into logical subtasks."
        )
        self.assertListEqual(result, ['Task 1', 'Task 2'])

    def test_generate_subtasks_empty(self):
        task = 'Simple Task'

        # Mock the brain response with no subtasks
        self.mock_brain.prompt.return_value = {}

        result = self.planner.generate_subtasks(task)
        self.assertListEqual(result, [])

if __name__ == '__main__':
    unittest.main()