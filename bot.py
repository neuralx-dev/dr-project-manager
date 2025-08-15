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
            [InlineKeyboardButton("📋 پروژه‌های من", callback_data="list_projects")],
            [InlineKeyboardButton("➕ ایجاد پروژه", callback_data="create_project")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"به ربات مدیریت پروژه خوش آمدید، {user.first_name}! 🚀\n\n"
            "پروژه‌ها، بخش‌ها و کارهای خود را به طور مؤثر مدیریت کنید.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
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
            await query.edit_message_text("نام پروژه را برایم ارسال کنید:")
            context.user_data['action'] = 'create_project'
        elif data.startswith("project_"):
            project_id = int(data.split("_")[1])
            await show_project(query, db, user, project_id)
        elif data.startswith("sections_"):
            project_id = int(data.split("_")[1])
            await show_sections(query, db, user, project_id)
        elif data.startswith("add_section_"):
            project_id = int(data.split("_")[2])
            await query.edit_message_text("نام بخش را برایم ارسال کنید:")
            context.user_data['action'] = f'add_section_{project_id}'
        elif data.startswith("section_"):
            section_id = int(data.split("_")[1])
            await show_tasks(query, db, user, section_id)
        elif data.startswith("add_task_"):
            section_id = int(data.split("_")[2])
            await query.edit_message_text("عنوان کار را برایم ارسال کنید:")
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
            await query.edit_message_text("شناسه تلگرام کاربری که می‌خواهید اضافه کنید را ارسال کنید:")
            context.user_data['action'] = f'add_member_{project_id}'
        elif data.startswith("set_channel_"):
            project_id = int(data.split("_")[2])
            await query.edit_message_text("شناسه کانال را ارسال کنید (با @channel_name یا -100xxxxxxxxx):")
            context.user_data['action'] = f'set_channel_{project_id}'
        elif data == "back_to_main":
            keyboard = [
                [InlineKeyboardButton("📋 پروژه‌های من", callback_data="list_projects")],
                [InlineKeyboardButton("➕ ایجاد پروژه", callback_data="create_project")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("منوی اصلی:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in button handler: {e}")
        await query.edit_message_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
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
            keyboard = [[InlineKeyboardButton("➕ ایجاد پروژه", callback_data="create_project")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("هیچ پروژه‌ای یافت نشد. اولین پروژه خود را ایجاد کنید!", reply_markup=reply_markup)
            return
        
        keyboard = []
        for project in projects:
            role = "👑 مالک" if project.owner_id == user.id else "👤 عضو"
            keyboard.append([InlineKeyboardButton(
                f"{project.name} ({role})", 
                callback_data=f"project_{project.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("➕ ایجاد پروژه", callback_data="create_project")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("پروژه‌های شما:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in list_projects: {e}")
        await query.edit_message_text("❌ خطایی در بارگذاری پروژه‌ها رخ داد.")

async def show_project(query, db: Session, user: User, project_id: int):
    """Show project details - FIXED: Added proper error handling"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            await query.edit_message_text("پروژه یافت نشد.")
            return
        
        # Check access - FIXED: Use proper relationship checking
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("پروژه یافت نشد یا دسترسی رد شد.")
            return
        
        sections_count = len(project.sections)
        tasks_count = sum(len(section.tasks) for section in project.sections)
        
        text = f"📋 **{project.name}**\n\n"
        text += f"📄 توضیحات: {project.description or 'بدون توضیحات'}\n"
        text += f"📊 بخش‌ها: {sections_count}\n"
        text += f"✅ کل کارها: {tasks_count}\n"
        text += f"👑 مالک: {project.owner.first_name}\n"
        text += f"👥 اعضا: {len(project.members)}\n"
        if project.channel_id:
            text += f"📢 کانال به‌روزرسانی: {project.channel_id}\n"
        
        keyboard = [
            [InlineKeyboardButton("📂 مشاهده بخش‌ها", callback_data=f"sections_{project.id}")],
            [InlineKeyboardButton("➕ افزودن بخش", callback_data=f"add_section_{project.id}")],
        ]
        
        if project.owner_id == user.id:
            keyboard.extend([
                [InlineKeyboardButton("👥 افزودن عضو", callback_data=f"add_member_{project.id}")],
                [InlineKeyboardButton("📢 تنظیم کانال", callback_data=f"set_channel_{project.id}")],
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="list_projects")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in show_project: {e}")
        await query.edit_message_text("❌ خطایی در بارگذاری جزئیات پروژه رخ داد.")

async def show_sections(query, db: Session, user: User, project_id: int):
    """Show sections - FIXED: Added proper error handling"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            await query.edit_message_text("پروژه یافت نشد.")
            return
        
        # Check access
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("پروژه یافت نشد یا دسترسی رد شد.")
            return
        
        sections = project.sections
        if not sections:
            keyboard = [
                [InlineKeyboardButton("➕ افزودن بخش", callback_data=f"add_section_{project.id}")],
                [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"project_{project.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("هیچ بخشی یافت نشد.", reply_markup=reply_markup)
            return
        
        keyboard = []
        for section in sections:
            tasks_count = len(section.tasks)
            keyboard.append([InlineKeyboardButton(
                f"📂 {section.name} ({tasks_count} کار)", 
                callback_data=f"section_{section.id}"
            )])
        
        keyboard.extend([
            [InlineKeyboardButton("➕ افزودن بخش", callback_data=f"add_section_{project.id}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"project_{project.id}")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"بخش‌های {project.name}:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in show_sections: {e}")
        await query.edit_message_text("❌ خطایی در بارگذاری بخش‌ها رخ داد.")

async def show_tasks(query, db: Session, user: User, section_id: int):
    """Show tasks - FIXED: Added proper error handling"""
    try:
        section = db.query(Section).filter(Section.id == section_id).first()
        if not section:
            await query.edit_message_text("بخش یافت نشد.")
            return
        
        # FIXED: Check if section has project relationship
        if not hasattr(section, 'project') or section.project is None:
            await query.edit_message_text("بخش هیچ پروژه مرتبطی ندارد.")
            return
        
        project = section.project
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("دسترسی رد شد.")
            return
        
        tasks = section.tasks
        if not tasks:
            keyboard = [
                [InlineKeyboardButton("➕ افزودن کار", callback_data=f"add_task_{section.id}")],
                [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"sections_{project.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("هیچ کاری یافت نشد.", reply_markup=reply_markup)
            return
        
        keyboard = []
        for task in tasks:
            status_emoji = {"todo": "⭕", "in_progress": "🔄", "done": "✅"}
            keyboard.append([InlineKeyboardButton(
                f"{status_emoji.get(task.status, '⭕')} {task.title}", 
                callback_data=f"task_{task.id}"
            )])
        
        keyboard.extend([
            [InlineKeyboardButton("➕ افزودن کار", callback_data=f"add_task_{section.id}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"sections_{project.id}")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"کارهای {section.name}:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in show_tasks: {e}")
        await query.edit_message_text("❌ خطایی در بارگذاری کارها رخ داد.")

async def show_task(query, db: Session, user: User, task_id: int):
    """Show task details - FIXED: Added proper error handling"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await query.edit_message_text("کار یافت نشد.")
            return
        
        # FIXED: Check if task has section and project relationships
        if not hasattr(task, 'section') or task.section is None:
            await query.edit_message_text("کار هیچ بخش مرتبطی ندارد.")
            return
        
        if not hasattr(task.section, 'project') or task.section.project is None:
            await query.edit_message_text("بخش کار هیچ پروژه مرتبطی ندارد.")
            return
        
        project = task.section.project
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("دسترسی رد شد.")
            return
        
        status_emoji = {"todo": "⭕", "in_progress": "🔄", "done": "✅"}
        status_text = {"todo": "باید انجام شود", "in_progress": "در حال انجام", "done": "تکمیل شده"}
        text = f"{status_emoji.get(task.status, '⭕')} **{task.title}**\n\n"
        text += f"📄 توضیحات: {task.description or 'بدون توضیحات'}\n"
        text += f"📊 وضعیت: {status_text.get(task.status, 'نامشخص')}\n"
        text += f"👤 واگذار شده به: {task.assigned_to.first_name if task.assigned_to else 'واگذار نشده'}\n"
        text += f"📅 تاریخ ایجاد: {task.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("⭕ باید انجام شود", callback_data=f"status_{task.id}_todo"),
                InlineKeyboardButton("🔄 در حال انجام", callback_data=f"status_{task.id}_in_progress"),
                InlineKeyboardButton("✅ تکمیل شده", callback_data=f"status_{task.id}_done"),
            ],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"section_{task.section.id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in show_task: {e}")
        await query.edit_message_text("❌ خطایی در بارگذاری جزئیات کار رخ داد.")

async def update_task_status(query, db: Session, user: User, task_id: int, new_status: str):
    """Update task status - FIXED: Added proper error handling"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await query.edit_message_text("کار یافت نشد.")
            return
        
        # FIXED: Check relationships
        if not hasattr(task, 'section') or task.section is None:
            await query.edit_message_text("کار هیچ بخش مرتبطی ندارد.")
            return
        
        if not hasattr(task.section, 'project') or task.section.project is None:
            await query.edit_message_text("بخش کار هیچ پروژه مرتبطی ندارد.")
            return
        
        project = task.section.project
        if project.owner_id != user.id and user not in project.members:
            await query.edit_message_text("دسترسی رد شد.")
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
        await query.edit_message_text("❌ خطایی در به‌روزرسانی وضعیت کار رخ داد.")

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
            
            keyboard = [[InlineKeyboardButton("📋 مشاهده پروژه‌ها", callback_data="list_projects")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ پروژه '{text}' با موفقیت ایجاد شد!",
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
                
                keyboard = [[InlineKeyboardButton("📂 مشاهده بخش‌ها", callback_data=f"sections_{project_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ بخش '{text}' با موفقیت اضافه شد!",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("❌ پروژه یافت نشد یا دسترسی رد شد.")
        
        elif action.startswith('add_task_'):
            section_id = int(action.split('_')[2])
            section = db.query(Section).filter(Section.id == section_id).first()
            
            if section:
                # FIXED: Check project relationship
                if not hasattr(section, 'project') or section.project is None:
                    await update.message.reply_text("❌ بخش هیچ پروژه مرتبطی ندارد.")
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
                    
                    keyboard = [[InlineKeyboardButton("📝 مشاهده کارها", callback_data=f"section_{section_id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"✅ کار '{text}' با موفقیت اضافه شد!",
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text("❌ دسترسی رد شد.")
            else:
                await update.message.reply_text("❌ بخش یافت نشد.")
        
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
                            await update.message.reply_text(f"✅ کاربر {new_user.first_name} به پروژه اضافه شد!")
                        else:
                            await update.message.reply_text("❌ کاربر قبلاً عضو این پروژه است.")
                    else:
                        await update.message.reply_text("❌ کاربر یافت نشد. ابتدا باید ربات را شروع کنند.")
                except ValueError:
                    await update.message.reply_text("❌ شناسه تلگرام نامعتبر است. لطفاً یک شناسه عددی ارسال کنید.")
            else:
                await update.message.reply_text("❌ پروژه یافت نشد یا شما مالک نیستید.")
        
        elif action.startswith('set_channel_'):
            project_id = int(action.split('_')[2])
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if project and project.owner_id == user.id:
                project.channel_id = text
                db.commit()
                await update.message.reply_text(f"✅ کانال به‌روزرسانی به {text} تنظیم شد")
            else:
                await update.message.reply_text("❌ پروژه یافت نشد یا شما مالک نیستید.")
        
        # Clear the action
        del context.user_data['action']
        
    except Exception as e:
        logger.error(f"Error in message handler: {e}")
        await update.message.reply_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
    finally:
        db.close()

def main():
    """Main function"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ خطا: لطفاً توکن ربات خود را تنظیم کنید!")
        print("1. از @BotFather در تلگرام توکن دریافت کنید")
        print("2. 'YOUR_BOT_TOKEN_HERE' را با توکن واقعی خود جایگزین کنید")
        return
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        print("🚀 ربات در حال راه‌اندازی...")
        print("برای توقف Ctrl+C را فشار دهید")
        application.run_polling()
    except Exception as e:
        print(f"❌ خطا در راه‌اندازی ربات: {e}")
        print("مطمئن شوید که توکن ربات شما صحیح است!")

if __name__ == "__main__":
    main()