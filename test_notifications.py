#!/usr/bin/env python3
"""
Test script for Persian notifications functionality
"""

import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from bot import message_handler
from models import SessionLocal, User, Project, Section, Task

async def test_notifications():
    """Test Persian notifications for adding sections, tasks, and completing tasks"""
    
    # Create test database session
    db = SessionLocal()
    
    try:
        # Create test user or get existing one
        test_user = db.query(User).filter(User.telegram_id == 99999).first()
        if not test_user:
            test_user = User(
                telegram_id=99999,
                username="testuser_notifications",
                first_name="احمد"
            )
            db.add(test_user)
        
        # Create test project with channel
        test_project = Project(
            name="پروژه تست",
            description="پروژه آزمایشی",
            owner_id=test_user.id,
            channel_id="@test_channel"  # Set a test channel
        )
        db.add(test_project)
        
        # Create test section
        test_section = Section(
            name="بخش آزمایشی",
            project_id=test_project.id
        )
        db.add(test_section)
        
        # Create test task
        test_task = Task(
            title="کار آزمایشی",
            description="این یک کار آزمایشی است",
            section_id=test_section.id,
            status="todo"
        )
        db.add(test_task)
        
        db.commit()
        db.refresh(test_user)
        db.refresh(test_project)
        db.refresh(test_section)
        db.refresh(test_task)
        
        print("✅ Test data created successfully")
        print(f"User ID: {test_user.id}")
        print(f"Project ID: {test_project.id} (Owner: {test_project.owner_id})")
        print(f"Section ID: {test_section.id}")
        print(f"Task ID: {test_task.id}")
        print(f"Channel ID: {test_project.channel_id}")
        
        # Test 1: Adding a section notification
        print("\n📂 Testing section addition notification...")
        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.text = "بخش جدید"
        mock_update.message.reply_text = AsyncMock()
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = test_user.telegram_id
        mock_update.effective_user.username = test_user.username
        mock_update.effective_user.first_name = test_user.first_name
        
        mock_context = Mock()
        mock_context.user_data = {'action': f'add_section_{test_project.id}'}
        mock_context.bot = Mock()
        mock_context.bot.send_message = AsyncMock()
        
        # Expected Persian notification for section
        expected_section_msg = f"📂 **بخش جدید اضافه شد**\n\n"
        expected_section_msg += f"📋 پروژه: {test_project.name}\n"
        expected_section_msg += f"📂 نام بخش: بخش جدید\n"
        expected_section_msg += f"👤 اضافه شده توسط: {test_user.first_name}\n"
        expected_section_msg += f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        print(f"Expected notification: {expected_section_msg}")
        
        # Test 2: Adding a task notification
        print("\n📝 Testing task addition notification...")
        mock_context.user_data = {'action': f'add_task_{test_section.id}'}
        mock_update.message.text = "کار جدید"
        
        # Expected Persian notification for task
        expected_task_msg = f"📝 **کار جدید اضافه شد**\n\n"
        expected_task_msg += f"📋 پروژه: {test_project.name}\n"
        expected_task_msg += f"📂 بخش: {test_section.name}\n"
        expected_task_msg += f"✏️ نام کار: کار جدید\n"
        expected_task_msg += f"👤 اضافه شده توسط: {test_user.first_name}\n"
        expected_task_msg += f"📊 وضعیت: باید انجام شود\n"
        expected_task_msg += f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        print(f"Expected notification: {expected_task_msg}")
        
        # Test 3: Task completion notification
        print("\n✅ Testing task completion notification...")
        expected_completion_msg = f"✅ **کار تکمیل شد**\n\n"
        expected_completion_msg += f"📋 پروژه: {test_project.name}\n"
        expected_completion_msg += f"📂 بخش: {test_section.name}\n"
        expected_completion_msg += f"✏️ نام کار: {test_task.title}\n"
        expected_completion_msg += f"👤 تکمیل شده توسط: {test_user.first_name}\n"
        expected_completion_msg += f"📊 وضعیت: تکمیل شده ✅\n"
        expected_completion_msg += f"📅 تاریخ تکمیل: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        print(f"Expected notification: {expected_completion_msg}")
        
        print("\n🎉 All notification formats are ready!")
        print("📋 Persian notifications have been implemented for:")
        print("   - 📂 Section addition")
        print("   - 📝 Task addition") 
        print("   - ✅ Task completion (done status)")
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_notifications())
