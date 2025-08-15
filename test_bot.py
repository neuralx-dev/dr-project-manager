import unittest
import asyncio
import os
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Import bot functions
from bot import (
    get_or_create_user, list_projects, show_project, show_sections, 
    show_tasks, show_task, update_task_status, message_handler
)
from models import Base, User, Project, Section, Task

class TestBotFunctions(unittest.TestCase):
    """Test suite for Telegram bot functions"""
    
    def setUp(self):
        """Set up test database and mock objects"""
        # Create in-memory SQLite database for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create test session
        self.db = self.SessionLocal()
        
        # Create mock user
        self.mock_user = Mock()
        self.mock_user.id = 12345
        self.mock_user.username = "testuser"
        self.mock_user.first_name = "Test User"
        
        # Create mock query object
        self.mock_query = Mock()
        self.mock_query.edit_message_text = AsyncMock()
        self.mock_query.answer = AsyncMock()
        self.mock_query.bot.send_message = AsyncMock()
        
        # Create mock update object
        self.mock_update = Mock()
        self.mock_update.message = Mock()
        self.mock_update.message.text = "Test Project"
        self.mock_update.message.reply_text = AsyncMock()
        self.mock_update.effective_user = self.mock_user
        
        # Create mock context
        self.mock_context = Mock()
        self.mock_context.user_data = {}
        
        # Create test data
        self.create_test_data()
    
    def create_test_data(self):
        """Create test data in the database"""
        # Create test user
        self.test_user = User(
            telegram_id=12345,
            username="testuser",
            first_name="Test User"
        )
        self.db.add(self.test_user)
        
        # Create test project
        self.test_project = Project(
            name="Test Project",
            description="A test project",
            owner_id=self.test_user.id
        )
        self.db.add(self.test_project)
        
        # Create test section
        self.test_section = Section(
            name="Test Section",
            project_id=self.test_project.id
        )
        self.db.add(self.test_section)
        
        # Create test task
        self.test_task = Task(
            title="Test Task",
            description="A test task",
            section_id=self.test_section.id,
            status="todo"
        )
        self.db.add(self.test_task)
        
        # Create another user for member testing
        self.test_user2 = User(
            telegram_id=67890,
            username="testuser2",
            first_name="Test User 2"
        )
        self.db.add(self.test_user2)
        
        self.db.commit()
        self.db.refresh(self.test_user)
        self.db.refresh(self.test_project)
        self.db.refresh(self.test_section)
        self.db.refresh(self.test_task)
        self.db.refresh(self.test_user2)
    
    def tearDown(self):
        """Clean up after tests"""
        self.db.close()
    
    def test_get_or_create_user_new_user(self):
        """Test creating a new user"""
        new_mock_user = Mock()
        new_mock_user.id = 99999
        new_mock_user.username = "newuser"
        new_mock_user.first_name = "New User"
        
        user = get_or_create_user(self.db, new_mock_user)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.telegram_id, 99999)
        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.first_name, "New User")
    
    def test_get_or_create_user_existing_user(self):
        """Test getting existing user"""
        user = get_or_create_user(self.db, self.mock_user)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.test_user.id)
        self.assertEqual(user.telegram_id, 12345)
    
    def test_list_projects_with_projects(self):
        """Test listing projects when user has projects"""
        # Test as owner
        asyncio.run(list_projects(self.mock_query, self.db, self.test_user))
        
        # Verify the function was called with correct text
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Your Projects:", call_args[0][0])
    
    def test_list_projects_no_projects(self):
        """Test listing projects when user has no projects"""
        # Create a user with no projects
        new_user = User(
            telegram_id=11111,
            username="noprojects",
            first_name="No Projects User"
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        
        asyncio.run(list_projects(self.mock_query, self.db, new_user))
        
        # Verify the function was called with "no projects" message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("No projects found", call_args[0][0])
    
    def test_list_projects_as_member(self):
        """Test listing projects when user is a member (not owner)"""
        # Add user as member to project
        self.test_project.members.append(self.test_user2)
        self.db.commit()
        
        asyncio.run(list_projects(self.mock_query, self.db, self.test_user2))
        
        # Verify the function was called
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_query.call_args
        self.assertIn("Your Projects:", call_args[0][0])
    
    def test_show_project_success(self):
        """Test showing project details successfully"""
        asyncio.run(show_project(self.mock_query, self.db, self.test_user, self.test_project.id))
        
        # Verify the function was called with project details
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Test Project", call_args[0][0])
        self.assertIn("Test Section", call_args[0][0])
    
    def test_show_project_access_denied(self):
        """Test showing project when access is denied"""
        # Try to access project with different user
        asyncio.run(show_project(self.mock_query, self.db, self.test_user2, self.test_project.id))
        
        # Verify access denied message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Project not found or access denied", call_args[0][0])
    
    def test_show_sections_success(self):
        """Test showing sections successfully"""
        asyncio.run(show_sections(self.mock_query, self.db, self.test_user, self.test_project.id))
        
        # Verify the function was called with sections
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Test Section", call_args[0][0])
    
    def test_show_sections_no_sections(self):
        """Test showing sections when project has no sections"""
        # Create project without sections
        empty_project = Project(
            name="Empty Project",
            owner_id=self.test_user.id
        )
        self.db.add(empty_project)
        self.db.commit()
        self.db.refresh(empty_project)
        
        asyncio.run(show_sections(self.mock_query, self.db, self.test_user, empty_project.id))
        
        # Verify "no sections" message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("No sections found", call_args[0][0])
    
    def test_show_tasks_success(self):
        """Test showing tasks successfully"""
        asyncio.run(show_tasks(self.mock_query, self.db, self.test_user, self.test_section.id))
        
        # Verify the function was called with tasks
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Test Task", call_args[0][0])
    
    def test_show_task_success(self):
        """Test showing task details successfully"""
        asyncio.run(show_task(self.mock_query, self.db, self.test_user, self.test_task.id))
        
        # Verify the function was called with task details
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Test Task", call_args[0][0])
        self.assertIn("todo", call_args[0][0])
    
    def test_update_task_status_success(self):
        """Test updating task status successfully"""
        old_status = self.test_task.status
        asyncio.run(update_task_status(self.mock_query, self.db, self.test_user, self.test_task.id, "done"))
        
        # Verify status was updated
        self.db.refresh(self.test_task)
        self.assertEqual(self.test_task.status, "done")
        
        # Verify the function was called to show updated task
        self.mock_query.edit_message_text.assert_called()
    
    def test_message_handler_create_project(self):
        """Test creating project through message handler"""
        self.mock_context.user_data['action'] = 'create_project'
        
        asyncio.run(message_handler(self.mock_update, self.mock_context))
        
        # Verify project was created
        project = self.db.query(Project).filter(Project.name == "Test Project").first()
        self.assertIsNotNone(project)
        self.assertEqual(project.owner_id, self.test_user.id)
        
        # Verify success message was sent
        self.mock_update.message.reply_text.assert_called_once()
        call_args = self.mock_update.message.reply_text.call_args
        self.assertIn("Project 'Test Project' created successfully", call_args[0][0])
    
    def test_message_handler_add_section(self):
        """Test adding section through message handler"""
        self.mock_context.user_data['action'] = f'add_section_{self.test_project.id}'
        
        asyncio.run(message_handler(self.mock_update, self.mock_context))
        
        # Verify section was created
        section = self.db.query(Section).filter(Section.name == "Test Project").first()
        self.assertIsNotNone(section)
        self.assertEqual(section.project_id, self.test_project.id)
    
    def test_message_handler_add_task(self):
        """Test adding task through message handler"""
        self.mock_context.user_data['action'] = f'add_task_{self.test_section.id}'
        
        asyncio.run(message_handler(self.mock_update, self.mock_context))
        
        # Verify task was created
        task = self.db.query(Task).filter(Task.title == "Test Project").first()
        self.assertIsNotNone(task)
        self.assertEqual(task.section_id, self.test_section.id)
    
    def test_message_handler_add_member_success(self):
        """Test adding member successfully"""
        self.mock_context.user_data['action'] = f'add_member_{self.test_project.id}'
        self.mock_update.message.text = "67890"  # test_user2's telegram_id
        
        asyncio.run(message_handler(self.mock_update, self.mock_context))
        
        # Verify member was added
        self.db.refresh(self.test_project)
        self.assertIn(self.test_user2, self.test_project.members)
    
    def test_message_handler_set_channel(self):
        """Test setting project channel"""
        self.mock_context.user_data['action'] = f'set_channel_{self.test_project.id}'
        self.mock_update.message.text = "@testchannel"
        
        asyncio.run(message_handler(self.mock_update, self.mock_context))
        
        # Verify channel was set
        self.db.refresh(self.test_project)
        self.assertEqual(self.test_project.channel_id, "@testchannel")
    
    def test_error_handling_invalid_project_id(self):
        """Test error handling for invalid project ID"""
        # Test with non-existent project ID
        asyncio.run(show_project(self.mock_query, self.db, self.test_user, 99999))
        
        # Verify error message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Project not found or access denied", call_args[0][0])
    
    def test_error_handling_invalid_section_id(self):
        """Test error handling for invalid section ID"""
        # Test with non-existent section ID
        asyncio.run(show_tasks(self.mock_query, self.db, self.test_user, 99999))
        
        # Verify error message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Section not found", call_args[0][0])
    
    def test_error_handling_invalid_task_id(self):
        """Test error handling for invalid task ID"""
        # Test with non-existent task ID
        asyncio.run(show_task(self.mock_query, self.db, self.test_user, 99999))
        
        # Verify error message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args
        self.assertIn("Task not found", call_args[0][0])

class TestDatabaseRelationships(unittest.TestCase):
    """Test database relationships and queries"""
    
    def setUp(self):
        """Set up test database"""
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
    
    def tearDown(self):
        """Clean up"""
        self.db.close()
    
    def test_project_members_relationship(self):
        """Test project members relationship works correctly"""
        # Create users
        user1 = User(telegram_id=1, username="user1", first_name="User 1")
        user2 = User(telegram_id=2, username="user2", first_name="User 2")
        self.db.add_all([user1, user2])
        
        # Create project
        project = Project(name="Test Project", owner_id=user1.id)
        self.db.add(project)
        
        # Add members
        project.members.append(user2)
        self.db.commit()
        self.db.refresh(project)
        
        # Test relationship
        self.assertIn(user2, project.members)
        self.assertEqual(len(project.members), 1)
    
    def test_project_query_with_members(self):
        """Test querying projects with members"""
        # Create users
        user1 = User(telegram_id=1, username="user1", first_name="User 1")
        user2 = User(telegram_id=2, username="user2", first_name="User 2")
        self.db.add_all([user1, user2])
        
        # Create project
        project = Project(name="Test Project", owner_id=user1.id)
        self.db.add(project)
        
        # Add members
        project.members.append(user2)
        self.db.commit()
        self.db.refresh(project)
        self.db.refresh(user2)
        
        # Test query - this is the problematic query from list_projects
        projects = self.db.query(Project).filter(
            (Project.owner_id == user2.id) | (Project.members.contains(user2))
        ).all()
        
        # This should return the project since user2 is a member
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].id, project.id)

if __name__ == '__main__':
    unittest.main()
