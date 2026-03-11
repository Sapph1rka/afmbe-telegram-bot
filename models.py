"""
Моделі бази даних для AFMBE Telegram Bot
Відповідає ТЗ для системи управління персонажами та кампаніями
"""
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, Float, 
    ForeignKey, DateTime, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()

# Enum для ролей доступу
class AccessRole(enum.Enum):
    GM = "GM"  # Повний контроль
    OWNER = "Owner"  # Основний гравець персонажа
    CONTROLLER = "Controller"  # Керування NPC / компаньйонами
    VIEWER = "Viewer"  # Перегляд без змін

# Enum для типів контейнерів
class ContainerType(enum.Enum):
    HAND = "hand"  # Рука
    POCKET = "pocket"  # Кишеня
    BACKPACK = "backpack"  # Рюкзак
    HOLSTER = "holster"  # Кобура
    ARMOR = "armor"  # Броня з підсумками
    OTHER = "other"  # Інше

# Enum для типів предметів
class ItemType(enum.Enum):
    WEAPON = "weapon"  # Зброя
    ARMOR = "armor"  # Броня
    AMMUNITION = "ammunition"  # Боєприпаси
    CONSUMABLE = "consumable"  # Витратні
    EQUIPMENT = "equipment"  # Спорядження
    OTHER = "other"  # Інше

# Enum для слотів броні/одягу
class ArmorSlot(enum.Enum):
    HEAD = "Голова"
    NECK = "Шия"
    TORSO = "Торс"
    ARMS = "Руки"
    HANDS = "Долоні"
    LEGS = "Ноги"
    FEET = "Ступні"

# Таблиця користувачів
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    character_accesses = relationship("CharacterAccess", back_populates="user", cascade="all, delete-orphan")
    active_character = relationship("ActiveCharacter", back_populates="user", uselist=False, cascade="all, delete-orphan")

# Таблиця GM (один GM на кампанію)
class GameMaster(Base):
    __tablename__ = 'game_masters'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Таблиця персонажів
class Character(Base):
    __tablename__ = 'characters'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    notes = Column(Text)  # Бекграунд, ГМ-коментарі
    experience = Column(Integer, default=0)
    general_state = Column(Text)  # Загальний стан
    is_npc = Column(Boolean, default=False)
    speed = Column(Integer, default=0)  # Швидкість персонажа
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Зв'язки
    accesses = relationship("CharacterAccess", back_populates="character", cascade="all, delete-orphan")
    attributes = relationship("CharacterAttribute", back_populates="character", cascade="all, delete-orphan")
    skills = relationship("CharacterSkill", back_populates="character", cascade="all, delete-orphan")
    resources = relationship("CharacterResource", back_populates="character", cascade="all, delete-orphan")
    traits = relationship("CharacterTrait", back_populates="character", cascade="all, delete-orphan")
    containers = relationship("Container", back_populates="character", cascade="all, delete-orphan")

# Таблиця доступу до персонажів (ACL)
class CharacterAccess(Base):
    __tablename__ = 'character_accesses'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)
    role = Column(SQLEnum(AccessRole), nullable=False, default=AccessRole.VIEWER)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    user = relationship("User", back_populates="character_accesses")
    character = relationship("Character", back_populates="accesses")
    
    # Унікальний індекс на пару user_id + character_id
    __table_args__ = (
        UniqueConstraint('user_id', 'character_id', name='uq_user_character_access'),
    )

# Таблиця активного персонажа користувача
class ActiveCharacter(Base):
    __tablename__ = 'active_characters'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Зв'язки
    user = relationship("User", back_populates="active_character")
    character = relationship("Character")

# Довідник статів
class Attribute(Base):
    __tablename__ = 'attributes'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    character_attributes = relationship("CharacterAttribute", back_populates="attribute")
    skills = relationship("Skill", back_populates="linked_attribute")

# Значення статів персонажів
class CharacterAttribute(Base):
    __tablename__ = 'character_attributes'
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)
    attribute_id = Column(Integer, ForeignKey('attributes.id'), nullable=False)
    value = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Зв'язки
    character = relationship("Character", back_populates="attributes")
    attribute = relationship("Attribute", back_populates="character_attributes")
    
    # Унікальний індекс на пару character_id + attribute_id
    __table_args__ = (
        UniqueConstraint('character_id', 'attribute_id', name='uq_character_attribute'),
    )

# Довідник навичок
class Skill(Base):
    __tablename__ = 'skills'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    parent_skill_id = Column(Integer, ForeignKey('skills.id'), nullable=True)  # Для ієрархії
    linked_attribute_id = Column(Integer, ForeignKey('attributes.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    linked_attribute = relationship("Attribute", back_populates="skills")
    parent_skill = relationship("Skill", remote_side=[id])
    character_skills = relationship("CharacterSkill", back_populates="skill")

# Значення навичок персонажів
class CharacterSkill(Base):
    __tablename__ = 'character_skills'
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)
    skill_id = Column(Integer, ForeignKey('skills.id'), nullable=False)
    level = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Зв'язки
    character = relationship("Character", back_populates="skills")
    skill = relationship("Skill", back_populates="character_skills")
    
    # Унікальний індекс на пару character_id + skill_id
    __table_args__ = (
        UniqueConstraint('character_id', 'skill_id', name='uq_character_skill'),
    )

# Довідник ресурсів
class Resource(Base):
    __tablename__ = 'resources'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    character_resources = relationship("CharacterResource", back_populates="resource")

# Значення ресурсів персонажів
class CharacterResource(Base):
    __tablename__ = 'character_resources'
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)
    resource_id = Column(Integer, ForeignKey('resources.id'), nullable=False)
    current_value = Column(Integer, default=0)
    max_value = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Зв'язки
    character = relationship("Character", back_populates="resources")
    resource = relationship("Resource", back_populates="character_resources")
    
    # Унікальний індекс на пару character_id + resource_id
    __table_args__ = (
        UniqueConstraint('character_id', 'resource_id', name='uq_character_resource'),
    )

# Черти персонажів (Qualities)
class CharacterTrait(Base):
    __tablename__ = 'character_traits'
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)
    name = Column(String(255), nullable=False)  # Назва черти
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    character = relationship("Character", back_populates="traits")
    
    # Унікальний індекс на пару character_id + name
    __table_args__ = (
        UniqueConstraint('character_id', 'name', name='uq_character_trait'),
    )

# Лог змін ресурсів
class ResourceChangeLog(Base):
    __tablename__ = 'resource_change_logs'
    
    id = Column(Integer, primary_key=True)
    character_resource_id = Column(Integer, ForeignKey('character_resources.id'), nullable=False)
    old_value = Column(Integer)
    new_value = Column(Integer)
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    character_resource = relationship("CharacterResource")

# Контейнери інвентарю
class Container(Base):
    __tablename__ = 'containers'
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)
    name = Column(String(255), nullable=False)
    container_type = Column(SQLEnum(ContainerType), nullable=False)
    max_slots = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    character = relationship("Character", back_populates="containers")
    slots = relationship("Slot", back_populates="container", cascade="all, delete-orphan")

# Слоти в контейнерах
class Slot(Base):
    __tablename__ = 'slots'
    
    id = Column(Integer, primary_key=True)
    container_id = Column(Integer, ForeignKey('containers.id'), nullable=False)
    slot_number = Column(Integer, nullable=False)  # Номер слота в контейнері
    size = Column(Integer, default=1)  # Розмір слота
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    container = relationship("Container", back_populates="slots")
    item_instances = relationship("ItemInstance", back_populates="slot")

# Шаблони предметів
class ItemTemplate(Base):
    __tablename__ = 'item_templates'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    item_type = Column(SQLEnum(ItemType), nullable=False)
    weight = Column(Float, default=0.0)
    size = Column(Integer, default=1)  # Скільки слотів займає
    is_stackable = Column(Boolean, default=False)
    armor_value = Column(String(50))  # Захист для броні (наприклад "d4-1")
    armor_slot_type = Column(SQLEnum(ArmorSlot), nullable=True)  # Слот для броні/одягу
    damage = Column(String(50))  # Урон для зброї (наприклад "d6+2")
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Зв'язки
    item_instances = relationship("ItemInstance", back_populates="template")

# Екземпляри предметів
class ItemInstance(Base):
    __tablename__ = 'item_instances'
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)  # Персонаж, якому належить предмет
    template_id = Column(Integer, ForeignKey('item_templates.id'), nullable=False)
    slot_id = Column(Integer, ForeignKey('slots.id'), nullable=True)  # Може бути None якщо не в інвентарі
    quantity = Column(Integer, default=1)  # Для стакабельних предметів
    condition = Column(String(100))  # Стан предмета
    charges = Column(Integer)  # Заряд/кількість використань
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Зв'язки
    character = relationship("Character")
    template = relationship("ItemTemplate", back_populates="item_instances")
    slot = relationship("Slot", back_populates="item_instances")

