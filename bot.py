import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from sqlalchemy.orm import Session
from models import SessionLocal, User, Project, Section, Task
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token - you can set this as environment variable or replace directly
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
print(BOT_TOKEN)
def get_db():
    """Get database session - fixed to return session directly"""
    return SessionLocal()

def get_or_create_user(db: Session, telegram_user):
    """Get or create user - fixed error handling"""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_user.id).first()
        if not user:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        db.rollback()
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    db = get_db()
    try:
        user = get_or_create_user(db, update.effective_user)
        keyboard = [
            [InlineKeyboardButton("📋 My Projects", callback_data="list_projects")],
            [InlineKeyboardButton("➕ Create Project", callback_data="create_project")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Welcome to Project Manager Bot, {user.first_name}! 🚀\n\n"
            "Manage your projects, sections, and tasks efficiently.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")
    finally:
        db.close()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button callback handler"""
    query = update.callback_query
    await query.answer()
    
    db = get_db()
    try:
        user = get_or_create_user(db, update.effective_user)
        data = query.data
        
        if data == "list_projects":
            await list_projects(query, db, user)
        elif data == "create_project":
            await query.edit_message_text("Send me the project name:")
            context.user_data['action'] = 'create_project'
        elif data.startswith("project_"):
            project_id = int(data.split("_")[1])
            await show_project(query, db, user, project_id)
        elif data.startswith("sections_"):
            project_id = int(data.split("_")[1])
            await show_sections(query, db, user, project_id)
        elif data.startswith("add_section_"):
            project_id = int(data.split("_")[2])
            await query.edit_message_text("Send me the section name:")
            context.user_data['action'] = f'add_section_{project_id}'
        elif data.startswith("section_"):
            section_id = int(data.split("_")[1])
            await show_tasks(query, db, user, section_id)
        elif data.startswith("add_task_"):
            section_id = int(data.split("_")[2])
            await query.edit_message_text("Send me the task title:")
            context.user_data['action'] = f'add_task_{section_id}'
        elif data.startswith("task_"):
            task_id = int(data.split("_")[1])
            await show_task(query, db, user, task_id)
        elif data.startswith("status_"):
            parts = data.split("_")
            task_id, status = int(parts[1]), parts[2]
            await update_task_status(query, db, user, task_id, status)
        elif data.startswith("add_member_"):
            project_id = int(data.split("_")[2])
            await query.edit_message_text("Send me the Telegram ID of the user to add:")
            context.user_data['action'] = f'add_member_{project_id}'
        elif data.startswith("set_channel_"):
            project_id = int(data.split("_")[2])
            await query.edit_message_text("Send me the channel ID (with @channel_name or -100xxxxxxxxx):")
            context.user_data['action'] = f'set_channel_{project_id}'
        elif data == "back_to_main":
            keyboard = [
                [InlineKeyboardButton("📋 My Projects", callback_data="list_projects")],
                [InlineKeyboardButton("➕ Create Project", callback_data="create_project")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Main Menu:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in button handler: {e}")
        await query.edit_message_text("❌ An error occurred. Please try again.")
    finally:
        db.close()

async def list_projects(query, db: Session, user: User):
    """List projects - FIXED: Now properly queries projects for user"""
    try:
        # Fixed query: Use proper SQLAlchemy syntax for many-to-many relationships
        projects = db.query(Project).filter(
            (Project.owner_id == user.id) | 
            (Project.members.any(id=user.id))
        ).all()
        
        if not projects:
            keyboard = [[InlineKeyboardButton("➕ Create Project", callback_data="create_project")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("No projects found. Create your first project!", reply_markup=reply_markup)
            return
        
        keyboard = []
        for project in projects:
            role = "👑 Owner" if project.owner_id == user.id else "👤 Member"
            keyboard.append([InlineKeyboardButton(
                f"{project.name} ({role})", 
                callback_data=f"project_{project.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("➕ Create Project", callback_data="create_project")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Your Projects:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in list_projects: {e}")
        await query.edit_message_text("❌ An error occurred while loading projects.")

async def show_project(query, db: Session, user: User, project_id: int):
    """Show project details - FIXED: Added proper error handling"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            await query.edit_message_text("Project not found.")
            return
        
        # Check access - FIXED: Use proper relationship checking
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("Project not found or access denied.")
            return
        
        sections_count = len(project.sections)
        tasks_count = sum(len(section.tasks) for section in project.sections)
        
        text = f"📋 **{project.name}**\n\n"
        text += f"📄 Description: {project.description or 'No description'}\n"
        text += f"📊 Sections: {sections_count}\n"
        text += f"✅ Total Tasks: {tasks_count}\n"
        text += f"👑 Owner: {project.owner.first_name}\n"
        text += f"👥 Members: {len(project.members)}\n"
        if project.channel_id:
            text += f"📢 Updates Channel: {project.channel_id}\n"
        
        keyboard = [
            [InlineKeyboardButton("📂 View Sections", callback_data=f"sections_{project.id}")],
            [InlineKeyboardButton("➕ Add Section", callback_data=f"add_section_{project.id}")],
        ]
        
        if project.owner_id == user.id:
            keyboard.extend([
                [InlineKeyboardButton("👥 Add Member", callback_data=f"add_member_{project.id}")],
                [InlineKeyboardButton("📢 Set Channel", callback_data=f"set_channel_{project.id}")],
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="list_projects")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in show_project: {e}")
        await query.edit_message_text("❌ An error occurred while loading project details.")

async def show_sections(query, db: Session, user: User, project_id: int):
    """Show sections - FIXED: Added proper error handling"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            await query.edit_message_text("Project not found.")
            return
        
        # Check access
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("Project not found or access denied.")
            return
        
        sections = project.sections
        if not sections:
            keyboard = [
                [InlineKeyboardButton("➕ Add Section", callback_data=f"add_section_{project.id}")],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"project_{project.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("No sections found.", reply_markup=reply_markup)
            return
        
        keyboard = []
        for section in sections:
            tasks_count = len(section.tasks)
            keyboard.append([InlineKeyboardButton(
                f"📂 {section.name} ({tasks_count} tasks)", 
                callback_data=f"section_{section.id}"
            )])
        
        keyboard.extend([
            [InlineKeyboardButton("➕ Add Section", callback_data=f"add_section_{project.id}")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"project_{project.id}")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Sections in {project.name}:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in show_sections: {e}")
        await query.edit_message_text("❌ An error occurred while loading sections.")

async def show_tasks(query, db: Session, user: User, section_id: int):
    """Show tasks - FIXED: Added proper error handling"""
    try:
        section = db.query(Section).filter(Section.id == section_id).first()
        if not section:
            await query.edit_message_text("Section not found.")
            return
        
        # FIXED: Check if section has project relationship
        if not hasattr(section, 'project') or section.project is None:
            await query.edit_message_text("Section has no associated project.")
            return
        
        project = section.project
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("Access denied.")
            return
        
        tasks = section.tasks
        if not tasks:
            keyboard = [
                [InlineKeyboardButton("➕ Add Task", callback_data=f"add_task_{section.id}")],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"sections_{project.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("No tasks found.", reply_markup=reply_markup)
            return
        
        keyboard = []
        for task in tasks:
            status_emoji = {"todo": "⭕", "in_progress": "🔄", "done": "✅"}
            keyboard.append([InlineKeyboardButton(
                f"{status_emoji.get(task.status, '⭕')} {task.title}", 
                callback_data=f"task_{task.id}"
            )])
        
        keyboard.extend([
            [InlineKeyboardButton("➕ Add Task", callback_data=f"add_task_{section.id}")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"sections_{project.id}")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Tasks in {section.name}:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in show_tasks: {e}")
        await query.edit_message_text("❌ An error occurred while loading tasks.")

async def show_task(query, db: Session, user: User, task_id: int):
    """Show task details - FIXED: Added proper error handling"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await query.edit_message_text("Task not found.")
            return
        
        # FIXED: Check if task has section and project relationships
        if not hasattr(task, 'section') or task.section is None:
            await query.edit_message_text("Task has no associated section.")
            return
        
        if not hasattr(task.section, 'project') or task.section.project is None:
            await query.edit_message_text("Task section has no associated project.")
            return
        
        project = task.section.project
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("Access denied.")
            return
        
        status_emoji = {"todo": "⭕", "in_progress": "🔄", "done": "✅"}
        text = f"{status_emoji.get(task.status, '⭕')} **{task.title}**\n\n"
        text += f"📄 Description: {task.description or 'No description'}\n"
        text += f"📊 Status: {task.status.replace('_', ' ').title()}\n"
        text += f"👤 Assigned to: {task.assigned_to.first_name if task.assigned_to else 'Unassigned'}\n"
        text += f"📅 Created: {task.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("⭕ To Do", callback_data=f"status_{task.id}_todo"),
                InlineKeyboardButton("🔄 In Progress", callback_data=f"status_{task.id}_in_progress"),
                InlineKeyboardButton("✅ Done", callback_data=f"status_{task.id}_done"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"section_{task.section.id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in show_task: {e}")
        await query.edit_message_text("❌ An error occurred while loading task details.")

async def update_task_status(query, db: Session, user: User, task_id: int, new_status: str):
    """Update task status - FIXED: Added proper error handling"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await query.edit_message_text("Task not found.")
            return
        
        # FIXED: Check relationships
        if not hasattr(task, 'section') or task.section is None:
            await query.edit_message_text("Task has no associated section.")
            return
        
        if not hasattr(task.section, 'project') or task.section.project is None:
            await query.edit_message_text("Task section has no associated project.")
            return
        
        project = task.section.project
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("Access denied.")
            return
        
        old_status = task.status
        task.status = new_status
        db.commit()
        
        # Send notification to channel only when task is marked as done
        if project.channel_id and new_status == "done":
            try:
                logger.info(f"Attempting to send completion notification to channel: {project.channel_id}")
                notification_message = f"✅ **کار تکمیل شد**\n\n"
                notification_message += f"📋 پروژه: {project.name}\n"
                notification_message += f"📂 بخش: {task.section.name}\n"
                notification_message += f"✏️ نام کار: {task.title}\n"
                notification_message += f"👤 تکمیل شده توسط: {user.first_name}\n"
                notification_message += f"📊 وضعیت: تکمیل شده ✅\n"
                notification_message += f"📅 تاریخ تکمیل: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                
                await query.bot.send_message(
                    chat_id=project.channel_id,
                    text=notification_message,
                    parse_mode='Markdown'
                )
                logger.info(f"Completion notification sent successfully to channel: {project.channel_id}")
            except Exception as e:
                logger.error(f"Failed to send completion notification to channel: {e}")
                logger.error(f"Channel ID: {project.channel_id}, Project: {project.name}")
        else:
            if not project.channel_id:
                logger.info(f"No channel configured for project: {project.name}")
            if new_status != "done":
                logger.info(f"Task status changed to {new_status}, no notification needed")
        
        await show_task(query, db, user, task_id)
    except Exception as e:
        logger.error(f"Error in update_task_status: {e}")
        await query.edit_message_text("❌ An error occurred while updating task status.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message handler - FIXED: Added proper error handling"""
    if 'action' not in context.user_data:
        return
    
    db = get_db()
    try:
        user = get_or_create_user(db, update.effective_user)
        action = context.user_data['action']
        text = update.message.text
        
        if action == 'create_project':
            project = Project(name=text, owner_id=user.id)
            db.add(project)
            db.commit()
            db.refresh(project)
            
            keyboard = [[InlineKeyboardButton("📋 View Projects", callback_data="list_projects")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Project '{text}' created successfully!",
                reply_markup=reply_markup
            )
            
        elif action.startswith('add_section_'):
            project_id = int(action.split('_')[2])
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if project and (project.owner_id == user.id or user in project.members):
                section = Section(name=text, project_id=project_id)
                db.add(section)
                db.commit()
                
                # Send notification to channel if configured
                if project.channel_id:
                    try:
                        logger.info(f"Attempting to send section notification to channel: {project.channel_id}")
                        notification_message = f"📂 **بخش جدید اضافه شد**\n\n"
                        notification_message += f"📋 پروژه: {project.name}\n"
                        notification_message += f"📂 نام بخش: {text}\n"
                        notification_message += f"👤 اضافه شده توسط: {user.first_name}\n"
                        notification_message += f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        
                        await update.bot.send_message(
                            chat_id=project.channel_id,
                            text=notification_message,
                            parse_mode='Markdown'
                        )
                        logger.info(f"Section notification sent successfully to channel: {project.channel_id}")
                    except Exception as e:
                        logger.error(f"Failed to send section notification to channel: {e}")
                        logger.error(f"Channel ID: {project.channel_id}, Project: {project.name}")
                else:
                    logger.info(f"No channel configured for project: {project.name}")
                
                keyboard = [[InlineKeyboardButton("📂 View Sections", callback_data=f"sections_{project_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ Section '{text}' added successfully!",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("❌ Project not found or access denied.")
        
        elif action.startswith('add_task_'):
            section_id = int(action.split('_')[2])
            section = db.query(Section).filter(Section.id == section_id).first()
            
            if section:
                # FIXED: Check project relationship
                if not hasattr(section, 'project') or section.project is None:
                    await update.message.reply_text("❌ Section has no associated project.")
                    return
                
                project = section.project
                if project.owner_id == user.id or user in project.members:
                    task = Task(title=text, section_id=section_id)
                    db.add(task)
                    db.commit()
                    
                    # Send notification to channel if configured
                    if project.channel_id:
                        try:
                            logger.info(f"Attempting to send task notification to channel: {project.channel_id}")
                            notification_message = f"📝 **کار جدید اضافه شد**\n\n"
                            notification_message += f"📋 پروژه: {project.name}\n"
                            notification_message += f"📂 بخش: {section.name}\n"
                            notification_message += f"✏️ نام کار: {text}\n"
                            notification_message += f"👤 اضافه شده توسط: {user.first_name}\n"
                            notification_message += f"📊 وضعیت: باید انجام شود\n"
                            notification_message += f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                            
                            await update.bot.send_message(
                                chat_id=project.channel_id,
                                text=notification_message,
                                parse_mode='Markdown'
                            )
                            logger.info(f"Task notification sent successfully to channel: {project.channel_id}")
                        except Exception as e:
                            logger.error(f"Failed to send task notification to channel: {e}")
                            logger.error(f"Channel ID: {project.channel_id}, Project: {project.name}")
                    else:
                        logger.info(f"No channel configured for project: {project.name}")
                    
                    keyboard = [[InlineKeyboardButton("📝 View Tasks", callback_data=f"section_{section_id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"✅ Task '{text}' added successfully!",
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text("❌ Access denied.")
            else:
                await update.message.reply_text("❌ Section not found.")
        
        elif action.startswith('add_member_'):
            project_id = int(action.split('_')[2])
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if project and project.owner_id == user.id:
                try:
                    telegram_id = int(text)
                    new_user = db.query(User).filter(User.telegram_id == telegram_id).first()
                    
                    if new_user:
                        if new_user not in project.members:
                            project.members.append(new_user)
                            db.commit()
                            await update.message.reply_text(f"✅ User {new_user.first_name} added to project!")
                        else:
                            await update.message.reply_text("❌ User is already a member of this project.")
                    else:
                        await update.message.reply_text("❌ User not found. They need to start the bot first.")
                except ValueError:
                    await update.message.reply_text("❌ Invalid Telegram ID. Please send a numeric ID.")
            else:
                await update.message.reply_text("❌ Project not found or you're not the owner.")
        
        elif action.startswith('set_channel_'):
            project_id = int(action.split('_')[2])
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if project and project.owner_id == user.id:
                project.channel_id = text
                db.commit()
                await update.message.reply_text(f"✅ Update channel set to: {text}")
            else:
                await update.message.reply_text("❌ Project not found or you're not the owner.")
        
        # Clear the action
        del context.user_data['action']
        
    except Exception as e:
        logger.error(f"Error in message handler: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")
    finally:
        db.close()

def main():
    """Main function"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: Please set your bot token!")
        print("1. Get a token from @BotFather on Telegram")
        print("2. Replace 'YOUR_BOT_TOKEN_HERE' with your actual token")
        return
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        print("🚀 Bot starting...")
        print("Press Ctrl+C to stop")
        application.run_polling()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        print("Make sure your bot token is correct!")

if __name__ == "__main__":
    main()