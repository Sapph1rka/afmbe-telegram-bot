"""
Модуль для роботи з базою даних
"""
import os
from sqlalchemy import create_engine, and_, or_, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from models import (
    Base, User, GameMaster, Character, CharacterAccess, ActiveCharacter,
    Attribute, CharacterAttribute, Skill, CharacterSkill,
    Resource, CharacterResource, ResourceChangeLog, CharacterTrait,
    Container, Slot, ItemTemplate, ItemInstance,
    AccessRole, ContainerType, ItemType, ArmorSlot
)
import logging

logger = logging.getLogger(__name__)

# Шлях до бази даних
DB_PATH = os.getenv('DB_PATH', 'afmbe_campaign.db')

# Створюємо движок БД
engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)

# Створюємо фабрику сесій
SessionLocal = sessionmaker(bind=engine)

def init_database():
    """Ініціалізує базу даних, створює всі таблиці"""
    Base.metadata.create_all(engine)
    logger.info(f"База даних ініціалізована: {DB_PATH}")
    
    # Виконуємо міграції
    run_migrations()
    
    # Ініціалізуємо базові дані
    init_default_data()

def run_migrations():
    """Виконує міграції бази даних"""
    session = SessionLocal()
    try:
        # Перевіряємо, чи існує таблиця item_instances
        result = session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='item_instances'
        """)).fetchone()
        
        if result:
            # Таблиця існує, перевіряємо чи є колонка character_id
            result = session.execute(text("""
                SELECT COUNT(*) as cnt 
                FROM pragma_table_info('item_instances') 
                WHERE name='character_id'
            """)).fetchone()
            
            if result and result[0] == 0:
                # Колонки немає, додаємо її
                logger.info("Додаю колонку character_id в таблицю item_instances...")
                session.execute(text("""
                    ALTER TABLE item_instances 
                    ADD COLUMN character_id INTEGER REFERENCES characters(id)
                """))
                
                # Видаляємо старі записи без character_id (вони некоректні)
                deleted = session.execute(text("""
                    DELETE FROM item_instances 
                    WHERE character_id IS NULL
                """)).rowcount
                
                if deleted > 0:
                    logger.info(f"Видалено {deleted} старих записів без character_id")
                
                session.commit()
                logger.info("Міграція виконана: додано character_id")
            else:
                logger.info("Міграція не потрібна: character_id вже існує")
        
        # Перевіряємо та додаємо колонку damage в item_templates
        result = session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='item_templates'
        """)).fetchone()
        
        if result:
            result = session.execute(text("""
                SELECT COUNT(*) as cnt 
                FROM pragma_table_info('item_templates') 
                WHERE name='damage'
            """)).fetchone()
            
            if result and result[0] == 0:
                logger.info("Додаю колонку damage в таблицю item_templates...")
                session.execute(text("""
                    ALTER TABLE item_templates 
                    ADD COLUMN damage VARCHAR(50)
                """))
                session.commit()
                logger.info("Міграція виконана: додано damage")
        
        # Міграція назв атрибутів на українську
        attribute_translations = {
            "Strength": "Сила",
            "Dexterity": "Спритність",
            "Constitution": "Статура",
            "Intelligence": "Інтелект",
            "Perception": "Уважність",
            "Willpower": "Воля"
        }
        
        # Оновлюємо існуючі записи зі старих назв на нові
        old_to_new = {
            "Сила волі": "Воля",
            "Сприйняття": "Уважність",
            "Тіло": "Статура"
        }
        
        for old_name, new_name in old_to_new.items():
            attr_old = session.query(Attribute).filter(Attribute.name == old_name).first()
            if attr_old:
                logger.info(f"Оновлюю назву атрибута: {old_name} -> {new_name}")
                attr_old.name = new_name
                session.commit()
        
        for eng_name, ukr_name in attribute_translations.items():
            attr = session.query(Attribute).filter(Attribute.name == eng_name).first()
            if attr:
                logger.info(f"Оновлюю назву атрибута: {eng_name} -> {ukr_name}")
                attr.name = ukr_name
                session.commit()
        
        # Міграція назв ресурсів на українську
        resource_translations = {
            "Endurance": "Витривалість",
            "Sanity": "Психіка",
            "Health Points": "Здоров'я"
        }
        
        for eng_name, ukr_name in resource_translations.items():
            res = session.query(Resource).filter(Resource.name == eng_name).first()
            if res:
                logger.info(f"Оновлюю назву ресурсу: {eng_name} -> {ukr_name}")
                res.name = ukr_name
                session.commit()
        
    except Exception as e:
        session.rollback()
        # Якщо таблиця не існує, це нормально - вона буде створена з новою структурою
        if "no such table" not in str(e).lower() and "no such column" not in str(e).lower():
            logger.warning(f"Помилка міграції: {e}")
    finally:
        session.close()

def init_default_data():
    """Ініціалізує базові довідники (стати, навички, ресурси)"""
    session = SessionLocal()
    try:
        # Базові стати для AFMBE (українською)
        default_attributes = [
            "Сила",
            "Спритність",
            "Статура",
            "Інтелект",
            "Уважність",
            "Воля"
        ]
        for attr_name in default_attributes:
            if not session.query(Attribute).filter(Attribute.name == attr_name).first():
                attr = Attribute(name=attr_name)
                session.add(attr)
        
        # Базові ресурси (українською)
        default_resources = [
            ("Витривалість", "Витривалість персонажа"),
            ("Психіка", "Психіка / Розум"),
            ("Здоров'я", "Очки здоров'я")
        ]
        for res_name, res_desc in default_resources:
            if not session.query(Resource).filter(Resource.name == res_name).first():
                res = Resource(name=res_name, description=res_desc)
                session.add(res)
        
        session.commit()
        logger.info("Базові довідники ініціалізовані")
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка ініціалізації базових даних: {e}")
    finally:
        session.close()

def get_user_by_telegram_id(telegram_id: int) -> User:
    """Отримує або створює користувача за telegram_id"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user
    finally:
        session.close()

def get_gm() -> GameMaster:
    """Отримує GM, якщо він є"""
    session = SessionLocal()
    try:
        return session.query(GameMaster).first()
    finally:
        session.close()

def set_gm(telegram_id: int) -> tuple[bool, str]:
    """Встановлює GM. Повертає (успіх, повідомлення)"""
    session = SessionLocal()
    try:
        # Перевіряємо, чи вже є GM
        existing_gm = session.query(GameMaster).first()
        if existing_gm:
            return False, "GM вже встановлений"
        
        gm = GameMaster(telegram_id=telegram_id)
        session.add(gm)
        session.commit()
        return True, "GM успішно встановлений"
    except IntegrityError:
        session.rollback()
        return False, "Помилка при встановленні GM"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка встановлення GM: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def create_character(name: str, is_npc: bool = False, notes: str = None) -> int:
    """Створює нового персонажа. Повертає ID персонажа"""
    session = SessionLocal()
    try:
        character = Character(name=name, is_npc=is_npc, notes=notes)
        session.add(character)
        session.flush()  # Отримуємо ID без commit
        
        character_id = character.id
        
        # Створюємо базові значення для всіх статів
        attributes = session.query(Attribute).all()
        for attr in attributes:
            char_attr = CharacterAttribute(character_id=character_id, attribute_id=attr.id, value=0)
            session.add(char_attr)
        
        # Створюємо базові значення для всіх ресурсів
        resources = session.query(Resource).all()
        for res in resources:
            char_res = CharacterResource(character_id=character_id, resource_id=res.id, current_value=0, max_value=0)
            session.add(char_res)
        
        session.commit()
        return character_id
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка створення персонажа: {e}")
        raise
    finally:
        session.close()

def grant_character_access(user_id: int, character_id: int, role: AccessRole) -> tuple[bool, str]:
    """Надає доступ користувачу до персонажа"""
    session = SessionLocal()
    try:
        # Перевіряємо, чи вже є доступ
        existing = session.query(CharacterAccess).filter(
            and_(
                CharacterAccess.user_id == user_id,
                CharacterAccess.character_id == character_id
            )
        ).first()
        
        if existing:
            existing.role = role
            session.commit()
            return True, "Доступ оновлено"
        
        access = CharacterAccess(user_id=user_id, character_id=character_id, role=role)
        session.add(access)
        session.commit()
        return True, "Доступ надано"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка надання доступу: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def get_user_characters(telegram_id: int) -> list[Character]:
    """Отримує список персонажів, до яких користувач має доступ"""
    session = SessionLocal()
    try:
        # GM має доступ до всіх персонажів
        gm = get_gm()
        if gm and gm.telegram_id == telegram_id:
            characters = session.query(Character).all()
            for char in characters:
                session.expunge(char)
            return characters
        
        user = get_user_by_telegram_id(telegram_id)
        accesses = session.query(CharacterAccess).filter(CharacterAccess.user_id == user.id).all()
        character_ids = [acc.character_id for acc in accesses]
        characters = session.query(Character).filter(Character.id.in_(character_ids)).all()
        # Від'єднуємо об'єкти від сесії, щоб їх можна було використовувати після закриття
        for char in characters:
            session.expunge(char)
        return characters
    finally:
        session.close()

def set_active_character(telegram_id: int, character_id: int) -> tuple[bool, str]:
    """Встановлює активного персонажа для користувача"""
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(telegram_id)
        
        # GM має доступ до всіх персонажів
        gm = get_gm()
        is_gm = gm and gm.telegram_id == telegram_id
        
        if not is_gm:
            # Перевіряємо доступ для звичайних користувачів
            access = session.query(CharacterAccess).filter(
                and_(
                    CharacterAccess.user_id == user.id,
                    CharacterAccess.character_id == character_id
                )
            ).first()
            
            if not access:
                return False, "У вас немає доступу до цього персонажа"
        
        # Перевіряємо, чи персонаж існує
        character = session.query(Character).filter(Character.id == character_id).first()
        if not character:
            return False, "Персонаж не знайдено"
        
        # Встановлюємо активного персонажа
        active = session.query(ActiveCharacter).filter(ActiveCharacter.user_id == user.id).first()
        if active:
            active.character_id = character_id
        else:
            active = ActiveCharacter(user_id=user.id, character_id=character_id)
            session.add(active)
        
        session.commit()
        return True, "Активний персонаж встановлено"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка встановлення активного персонажа: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def get_active_character(telegram_id: int) -> Character:
    """Отримує активного персонажа користувача"""
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(telegram_id)
        active = session.query(ActiveCharacter).filter(ActiveCharacter.user_id == user.id).first()
        if active:
            character = session.query(Character).filter(Character.id == active.character_id).first()
            if character:
                # Від'єднуємо об'єкт від сесії
                session.expunge(character)
            return character
        return None
    finally:
        session.close()

def check_character_access(telegram_id: int, character_id: int, required_roles: list[AccessRole] = None) -> tuple[bool, AccessRole]:
    """Перевіряє доступ користувача до персонажа. Повертає (має доступ, роль)"""
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(telegram_id)
        
        # GM має повний доступ
        gm = get_gm()
        if gm and gm.telegram_id == telegram_id:
            return True, AccessRole.GM
        
        access = session.query(CharacterAccess).filter(
            and_(
                CharacterAccess.user_id == user.id,
                CharacterAccess.character_id == character_id
            )
        ).first()
        
        if not access:
            return False, None
        
        if required_roles and access.role not in required_roles:
            return False, access.role
        
        return True, access.role
    finally:
        session.close()

def set_attribute_value(character_id: int, attribute_name: str, value: int) -> tuple[bool, str]:
    """Встановлює значення стати персонажа"""
    session = SessionLocal()
    try:
        attribute = session.query(Attribute).filter(Attribute.name == attribute_name).first()
        if not attribute:
            return False, f"Стата '{attribute_name}' не знайдена"
        
        char_attr = session.query(CharacterAttribute).filter(
            and_(
                CharacterAttribute.character_id == character_id,
                CharacterAttribute.attribute_id == attribute.id
            )
        ).first()
        
        if not char_attr:
            char_attr = CharacterAttribute(character_id=character_id, attribute_id=attribute.id, value=value)
            session.add(char_attr)
        else:
            char_attr.value = value
        
        session.commit()
        return True, f"Стата '{attribute_name}' встановлена на {value}"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка встановлення стати: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def set_skill_level(character_id: int, skill_name: str, level: int) -> tuple[bool, str]:
    """Встановлює рівень навички персонажа. Створює навичку, якщо її немає."""
    session = SessionLocal()
    try:
        skill = session.query(Skill).filter(Skill.name == skill_name).first()
        if not skill:
            # Створюємо навичку, якщо її немає
            skill = Skill(name=skill_name)
            session.add(skill)
            session.flush()
        
        char_skill = session.query(CharacterSkill).filter(
            and_(
                CharacterSkill.character_id == character_id,
                CharacterSkill.skill_id == skill.id
            )
        ).first()
        
        if not char_skill:
            char_skill = CharacterSkill(character_id=character_id, skill_id=skill.id, level=level)
            session.add(char_skill)
        else:
            char_skill.level = level
        
        session.commit()
        return True, f"Навичка '{skill_name}' встановлена на рівень {level}"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка встановлення навички: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def remove_skill(character_id: int, skill_name: str) -> tuple[bool, str]:
    """Видаляє навичку персонажа"""
    session = SessionLocal()
    try:
        skill = session.query(Skill).filter(Skill.name == skill_name).first()
        if not skill:
            return False, f"Навичка '{skill_name}' не знайдена"
        
        char_skill = session.query(CharacterSkill).filter(
            and_(
                CharacterSkill.character_id == character_id,
                CharacterSkill.skill_id == skill.id
            )
        ).first()
        
        if not char_skill:
            return False, f"Навичка '{skill_name}' не знайдена у персонажа"
        
        session.delete(char_skill)
        session.commit()
        return True, f"Навичка '{skill_name}' видалена"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка видалення навички: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def add_trait(character_id: int, trait_name: str) -> tuple[bool, str]:
    """Додає черту персонажа"""
    session = SessionLocal()
    try:
        character = session.query(Character).filter(Character.id == character_id).first()
        if not character:
            return False, "Персонаж не знайдено"
        
        # Перевіряємо, чи вже є така черта
        existing = session.query(CharacterTrait).filter(
            and_(
                CharacterTrait.character_id == character_id,
                CharacterTrait.name == trait_name
            )
        ).first()
        
        if existing:
            return False, f"Черта '{trait_name}' вже є у персонажа"
        
        trait = CharacterTrait(character_id=character_id, name=trait_name)
        session.add(trait)
        session.commit()
        return True, f"Черта '{trait_name}' додана"
    except IntegrityError:
        session.rollback()
        return False, f"Черта '{trait_name}' вже існує"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка додавання черти: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def remove_trait(character_id: int, trait_name: str) -> tuple[bool, str]:
    """Видаляє черту персонажа"""
    session = SessionLocal()
    try:
        trait = session.query(CharacterTrait).filter(
            and_(
                CharacterTrait.character_id == character_id,
                CharacterTrait.name == trait_name
            )
        ).first()
        
        if not trait:
            return False, f"Черта '{trait_name}' не знайдена"
        
        session.delete(trait)
        session.commit()
        return True, f"Черта '{trait_name}' видалена"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка видалення черти: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def set_resource_value(character_id: int, resource_name: str, current_value: int = None, max_value: int = None) -> tuple[bool, str]:
    """Встановлює значення ресурсу персонажа"""
    session = SessionLocal()
    try:
        resource = session.query(Resource).filter(Resource.name == resource_name).first()
        if not resource:
            return False, f"Ресурс '{resource_name}' не знайдено"
        
        char_res = session.query(CharacterResource).filter(
            and_(
                CharacterResource.character_id == character_id,
                CharacterResource.resource_id == resource.id
            )
        ).first()
        
        if not char_res:
            char_res = CharacterResource(
                character_id=character_id,
                resource_id=resource.id,
                current_value=current_value or 0,
                max_value=max_value or 0
            )
            session.add(char_res)
        else:
            if current_value is not None:
                old_value = char_res.current_value
                char_res.current_value = current_value
                # Логуємо зміну
                log = ResourceChangeLog(
                    character_resource_id=char_res.id,
                    old_value=old_value,
                    new_value=current_value,
                    reason="Зміна через /set"
                )
                session.add(log)
            if max_value is not None:
                char_res.max_value = max_value
        
        session.commit()
        return True, f"Ресурс '{resource_name}' оновлено"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка встановлення ресурсу: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def get_character_sheet(character_id: int) -> dict:
    """Отримує дані для листа персонажа"""
    session = SessionLocal()
    try:
        character = session.query(Character).filter(Character.id == character_id).first()
        if not character:
            return None
        
        # Стати
        attributes = session.query(CharacterAttribute, Attribute).join(
            Attribute, CharacterAttribute.attribute_id == Attribute.id
        ).filter(CharacterAttribute.character_id == character_id).all()
        
        attrs_dict = {attr.name: char_attr.value for char_attr, attr in attributes}
        
        # Навички
        skills = session.query(CharacterSkill, Skill).join(
            Skill, CharacterSkill.skill_id == Skill.id
        ).filter(CharacterSkill.character_id == character_id).all()
        
        skills_dict = {skill.name: char_skill.level for char_skill, skill in skills}
        
        # Черти
        traits = session.query(CharacterTrait).filter(
            CharacterTrait.character_id == character_id
        ).all()
        
        traits_list = [trait.name for trait in traits]
        
        # Ресурси
        resources = session.query(CharacterResource, Resource).join(
            Resource, CharacterResource.resource_id == Resource.id
        ).filter(CharacterResource.character_id == character_id).all()
        
        resources_dict = {
            res.name: {
                'current': char_res.current_value,
                'max': char_res.max_value
            }
            for char_res, res in resources
        }
        
        # Від'єднуємо об'єкт від сесії
        session.expunge(character)
        
        return {
            'character': character,
            'attributes': attrs_dict,
            'skills': skills_dict,
            'traits': traits_list,
            'resources': resources_dict
        }
    finally:
        session.close()

def get_character_inventory(character_id: int) -> dict:
    """Отримує інвентар персонажа. Повертає словник з бронею, зброєю та предметами"""
    session = SessionLocal()
    try:
        armor_items = []
        weapon_items = []
        other_items = []
        
        # Отримуємо всі ItemInstance без слотів для цього персонажа
        all_items = session.query(ItemInstance, ItemTemplate).join(
            ItemTemplate, ItemInstance.template_id == ItemTemplate.id
        ).filter(
            and_(
                ItemInstance.character_id == character_id,
                ItemInstance.slot_id == None
            )
        ).all()
        
        for item, template in all_items:
            item_data = {
                'name': template.name,
                'type': template.item_type.value,
                'quantity': item.quantity,
                'armor_value': template.armor_value,
                'armor_slot': template.armor_slot_type.value if template.armor_slot_type else None,
                'damage': template.damage
            }
            if template.item_type == ItemType.ARMOR:
                armor_items.append(item_data)
            elif template.item_type == ItemType.WEAPON:
                weapon_items.append(item_data)
            else:
                other_items.append(item_data)
        
        # Групуємо броню за слотами захисту
        armor_by_slot = {}
        for armor_item in armor_items:
            slot_name = armor_item['armor_slot'] or 'Інше'
            if slot_name not in armor_by_slot:
                armor_by_slot[slot_name] = []
            armor_by_slot[slot_name].append(armor_item)
        
        return {
            'armor': armor_by_slot,
            'weapons': weapon_items,
            'items': other_items
        }
    finally:
        session.close()

def add_item_template(name: str, item_type: ItemType, weight: float = 0.0, size: int = 1, 
                     is_stackable: bool = False, armor_value: str = None, 
                     armor_slot_type: ArmorSlot = None, damage: str = None, 
                     description: str = None) -> ItemTemplate:
    """Створює шаблон предмета"""
    session = SessionLocal()
    try:
        template = ItemTemplate(
            name=name,
            item_type=item_type,
            weight=weight,
            size=size,
            is_stackable=is_stackable,
            armor_value=armor_value,
            armor_slot_type=armor_slot_type,
            damage=damage,
            description=description
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        return template
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка створення шаблону предмета: {e}")
        raise
    finally:
        session.close()

def add_item_to_character(character_id: int, item_template_id: int, quantity: int = 1, 
                         container_id: int = None) -> tuple[bool, str]:
    """Додає предмет до персонажа. Предмети не розміщуються автоматично в слоти."""
    session = SessionLocal()
    try:
        character = session.query(Character).filter(Character.id == character_id).first()
        if not character:
            return False, "Персонаж не знайдено"
        
        template = session.query(ItemTemplate).filter(ItemTemplate.id == item_template_id).first()
        if not template:
            return False, "Шаблон предмета не знайдено"
        
        # Створюємо екземпляр предмета без слота (slot_id=None)
        # Користувачі самі будуть вказувати, де знаходиться предмет
        item = ItemInstance(
            character_id=character_id,
            template_id=item_template_id,
            quantity=quantity,
            slot_id=None  # Не розміщуємо автоматично
        )
        session.add(item)
        session.commit()
        
        return True, f"Предмет '{template.name}' додано"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка додавання предмета: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

def remove_item_from_character(character_id: int, item_name: str) -> tuple[bool, str]:
    """Видаляє предмет з інвентаря персонажа за назвою"""
    session = SessionLocal()
    try:
        character = session.query(Character).filter(Character.id == character_id).first()
        if not character:
            return False, "Персонаж не знайдено"
        
        # Знаходимо шаблон за назвою
        template = session.query(ItemTemplate).filter(ItemTemplate.name == item_name).first()
        if not template:
            return False, f"Предмет '{item_name}' не знайдено"
        
        # Знаходимо екземпляр предмета для цього персонажа
        item_instance = session.query(ItemInstance).filter(
            and_(
                ItemInstance.character_id == character_id,
                ItemInstance.template_id == template.id,
                ItemInstance.slot_id == None  # Тільки предмети без слотів
            )
        ).first()
        
        if not item_instance:
            return False, f"Предмет '{item_name}' не знайдено в інвентарі персонажа"
        
        # Видаляємо екземпляр
        session.delete(item_instance)
        session.commit()
        
        return True, f"Предмет '{item_name}' видалено з інвентаря"
    except Exception as e:
        session.rollback()
        logger.error(f"Помилка видалення предмета: {e}")
        return False, f"Помилка: {str(e)}"
    finally:
        session.close()

