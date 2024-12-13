seimport telebot
from telebot import types
from telebot import TeleBot, types
import threading
import mysql.connector
import math
import time
import bs4
import requests
import pytest
import datetime
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from mnemonic import Mnemonic
from ton.sync import TonlibClient
from tonsdk.contract.wallet import Wallets, WalletVersionEnum
from pathlib import Path
from pytoniq import LiteBalancer, WalletV4R2, Contract, LiteClientLike, WalletError, begin_cell
from pytoniq_core import Address
from dedust import Asset, Factory, PoolType, JettonRoot, VaultJetton, VaultNative, SwapParams
from stonfi import RouterV1
from stonfi.constants import ROUTER_V1_ADDRESS, PTON_V1_ADDRESS
import logging
from pytoniq_core.boc import Cell, Builder
from pytoniq_core.tlb.account import StateInit
from pytoniq_core.boc.address import Address
from pytoniq_core.tlb.custom.wallet import WalletMessage
import asyncio
import uuid
import random
import string
import aiohttp
import json
import math
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import re

# Replace 'YOUR_TOKEN' with your actual bot token
bot = telebot.TeleBot('6445422040:AAGCyzVtxCTn1mFytvnOonB-ZpPdoFCOFc0')

sent_messages = {}
sent_buttons = {}
user_wallet_creation_status = {}
last_messages = {}
user_sessions = {}
user_data ={}

router = RouterV1(address=ROUTER_V1_ADDRESS)

# Base URL for DeDust API
base_url = "https://api.dedust.io/v2"
toncenter_api_key = 'a2881e37de34b22e34dbe124600b86eb409183ff2060a07b4548f4e3ec8858a3'

DEFAULT_INVITER_REFERRAL_ID = "PUT_YOUR_REFERRAL_ID"

def fetch_metadata(address):
    url = f"https://tonapi.io/v2/jettons/{address}"
    headers = {
        'accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.content:  # Check for a successful response and non-empty content
            return response.json()
        else:
            return
    except requests.RequestException as e:
        return

def fetch_pools():
    url = f"{base_url}/pools"
    try:
        response = requests.get(url)
        response.raise_for_status()
        # Check if the response contains JSON data
        if response.content:
            return response.json()
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching pools: {e}")
        return None

db = mysql.connector.connect(
    host="url",
    user="user",
    password="password",
    database="databse",
    charset='utf8mb4'  # Use utf8mb4 character set

)

def is_user_admin(user_id):
    # Define the admin user ID
    admin_user_id = 5099082627

    # Check if the user ID matches the admin user ID
    return user_id == admin_user_id

def get_cursor(dictionary=False):
    try:
        db.ping(True)
    except mysql.connector.errors.InterfaceError:
        db.connect()

    cursor = db.cursor(dictionary=dictionary)

    # Ensure any previous unread results are handled
    try:
        while cursor.nextset():
            cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error handling unread result: {err}")

    return cursor

def setup_mysql_db():
    cursor = get_cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS callback_data
                     (id INT AUTO_INCREMENT PRIMARY KEY, wallet_name VARCHAR(255), contract_address VARCHAR(255), besc_amount FLOAT, token_amount FLOAT)''')
    db.commit()
    cursor.close()

setup_mysql_db()

def add_callback_data(wallet_name, contract_address, besc_amount, token_amount):
    cursor = get_cursor()
    cursor.execute("INSERT INTO callback_data (wallet_name, contract_address, besc_amount, token_amount) VALUES (%s, %s, %s, %s)",
                   (wallet_name, contract_address, besc_amount, token_amount))
    db.commit()
    last_id = cursor.lastrowid
    cursor.close()
    return last_id

def get_callback_data(data_id):
    cursor = get_cursor(dictionary=True)
    cursor.execute("SELECT wallet_name, contract_address, besc_amount, token_amount FROM callback_data WHERE id=%s", (data_id,))
    data = cursor.fetchone()
    cursor.close()
    if data:
        return data['wallet_name'], data['contract_address'], data['besc_amount'], data['token_amount']
    return None

cursor = get_cursor()

def create_exchange(user_id, to_currency, from_amount, recipient_address, to_network, from_currency, from_network):
    api_key = 'b122ed0f04f27d76cf9a6ed0d38f62e04d685752fb2736731731f43bd483551e'
    url = 'https://api.changenow.io/v2/exchange'

    headers = {
        'Content-Type': 'application/json',
        'x-changenow-api-key': api_key
    }

    payload = {
        'fromCurrency': from_currency,  # Assuming the from_currency is SOL for SOL🔁TON pair
        'toCurrency': to_currency,
        'fromNetwork': from_network,  # Assuming the from_network is SOL for SOL🔁TON pair
        'toNetwork': to_network,
        'fromAmount': from_amount,
        'address': recipient_address,
        'flow': 'standard',
        'type': 'direct'
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        return response.json()
    else:
        del user_data[user_id]
        send_message_and_record(user_id, f'Error: ```{response.text}```', parse_mode="MarkdownV2")
        return

# Improved regex pattern to match the jetton contract address
jetton_contract_address_pattern = r'^EQ[A-Za-z0-9_-]{48}$'

def get_user_wallet_address(user_id, wallet_name):
    cursor = get_cursor(dictionary=True)

    select_query = """
    SELECT non_bounceable_address FROM user_wallets
    WHERE user_id = %s AND wallet_name = %s
    """

    cursor.execute(select_query, (user_id, wallet_name))
    row = cursor.fetchone()

    if row:
        return row['non_bounceable_address']
    else:
        return None



cursor.execute("""
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INT PRIMARY KEY,
    gas_price DECIMAL(10, 2),
    gas_limit INT
)
""")

table_creation_query = """
CREATE TABLE IF NOT EXISTS `user_wallets` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` BIGINT NOT NULL,
  `wallet_name` VARCHAR(255) NOT NULL,
  `wallet_address` VARCHAR(255) NOT NULL,
  `bounceable_address` VARCHAR(255) NOT NULL,
  `non_bounceable_address` VARCHAR(255) NOT NULL,
  `seed` TEXT NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `unique_wallet` (`user_id`, `wallet_name`),
  INDEX `idx_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

table_ref_query = """
CREATE TABLE IF NOT EXISTS `user_referrals` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` BIGINT NOT NULL,
  `referral_id` VARCHAR(255) NOT NULL,
  `referral_count` INT DEFAULT 0,
  `referral_balance` DECIMAL(10, 2) DEFAULT 0.00,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `unique_referral_id` (`referral_id`),
  UNIQUE KEY `unique_user` (`user_id`),
  INDEX `idx_referrals` (`referral_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

cursor.execute(table_ref_query)
cursor.execute(table_creation_query)
db.commit()

user_settings = {}
swap_details_storage = {}
user_first_names = {}

# Define the list of pairs
pairs = [
    {"pair": "SOL 🔁 TON", "from_currency": "sol", "to_currency": "ton", "from_network": "sol", "to_network": "ton"},
    {"pair": "BSC 🔁 TON", "from_currency": "bnb", "to_currency": "ton", "from_network": "bsc", "to_network": "ton"},
    {"pair": "ETH 🔁 TON", "from_currency": "eth", "to_currency": "ton", "from_network": "eth", "to_network": "ton"},
    {"pair": "BASE 🔁 TON", "from_currency": "eth", "to_currency": "ton", "from_network": "base", "to_network": "ton"},
    {"pair": "AVAX 🔁 TON", "from_currency": "avax", "to_currency": "ton", "from_network": "cchain", "to_network": "ton"},
    {"pair": "CRO 🔁 TON", "from_currency": "cro", "to_currency": "ton", "from_network": "cro", "to_network": "ton"},
    # Add more pairs here as needed
]

def get_user_settings(user_id):
    cursor = get_cursor(dictionary=True)

    # Execute the SELECT statement to fetch the settings for the specified user_id
    cursor.execute('SELECT * FROM user_settings WHERE user_id = %s', (user_id,))

    # Fetch the first (and expected only) record from the result
    user_settings = cursor.fetchone()

    # Don't forget to close the cursor and the connection after use
    cursor.close()

    # Return the user settings. If no settings are found for the given user_id, it will return None
    return user_settings

async def fetch_ton_balance(wallet_address):
    try:
        api_url = f"https://tonapi.io/v2/accounts/{wallet_address}"
        headers = {
            'accept': 'application/json'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    balance = int(data.get('balance', 0))
                    status = data.get('status', 'unknown')
                    return balance, status
                else:
                    print(f"Error fetching balance: {response.status}")
                    return 0, 'unknown'
    except Exception as e:
        print(f"Error while fetching balance: {e}")
        return 0, 'unknown'

def get_all_user_ids():
    user_ids = []
    try:
        cursor = get_cursor()

        # SQL query to select distinct user_ids from user_referrals
        cursor.execute("SELECT DISTINCT user_id FROM user_referrals")
        user_ids = [row[0] for row in cursor.fetchall()]

        cursor.close()
    except (Exception, mysql.connector.Error) as error:
        print(f"Error while fetching user IDs from database: {error}")

    return user_ids

def save_user_settings(user_id, gas_price, gas_limit):
    cursor = get_cursor()

    # Use INSERT ... ON DUPLICATE KEY UPDATE syntax to either insert a new record or update an existing one
    query = """
    INSERT INTO user_settings (user_id, gas_price, gas_limit)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE gas_price = %s, gas_limit = %s;
    """

    # Notice that we're passing gas_price and gas_limit twice due to their usage in both VALUES and UPDATE clauses
    cursor.execute(query, (user_id, gas_price, gas_limit, gas_price, gas_limit))

    db.commit()
    cursor.close()

def user_is_new(user_id):
    cursor = get_cursor()
    try:
        cursor.execute("SELECT 1 FROM user_referrals WHERE user_id = %s", (user_id,))
        return cursor.fetchone() is None
    finally:
        cursor.close()

def fetch_order(order_id):
    cursor = get_cursor()
    cursor.execute('SELECT * FROM orders WHERE id = %s', (order_id,))
    order = cursor.fetchone()
    cursor.close()
    return order

def update_order_status(order_id, status):
    cursor = get_cursor()
    cursor.execute('UPDATE orders SET status = %s WHERE id = %s', (status, order_id))
    db.commit()
    cursor.close()

def generate_unique_referral_id(user_id):
    """
    Generates a unique referral ID for a user.

    Args:
    user_id (int): The user's Telegram ID.

    Returns:
    str: A unique referral ID.
    """
    # Generate a random string of letters and digits
    random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    return f"{user_id}-{random_part}"

def increment_referral_count(referral_id):
    cursor = get_cursor()
    try:
        # Update the total referrals count for the referrer
        cursor.execute("""
            UPDATE user_referrals
            SET total_referrals = total_referrals + 1
            WHERE referral_id = %s
        """, (referral_id,))
        db.commit()
    except Exception as e:
        print(f"Failed to increment referral count: {e}")
        db.rollback()  # Ensure changes are not saved if there's an error
    finally:
        cursor.close()

import mysql.connector

def get_default_wallet(user_id):
    cursor = get_cursor()
    try:
        # Fetch the default wallet for the user
        cursor.execute("""
            SELECT wallet_name
            FROM user_wallets
            WHERE user_id = %s AND is_default = TRUE
        """, (user_id,))
        default_wallet = cursor.fetchone()

        # Close the cursor and connection
        cursor.close()

        # Return the wallet name if found, otherwise None
        return default_wallet[0] if default_wallet else None

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return None




def fetch_user_orders(user_id):
    try:
        cursor = get_cursor()
        cursor.execute('''
        SELECT id, status, action, indicator, indicator_value, expiration, ton_amount, token_name, token_symbol, current_price, market_cap, buy_sell
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        ''', (user_id,))
        orders = cursor.fetchall()
        cursor.close()
        return orders
    except Exception as e:
        logging.error(f"Failed to fetch orders for user {user_id}: {e}")
        return []

def handle_new_user(user_id, inviter_referral_id):
    referral_id = generate_unique_referral_id(user_id)  # Generate a unique referral ID for the new user
    user_info = bot.get_chat(user_id)  # Fetch user info to get the username

    markup = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton("Buy", callback_data='buy_button'),
        types.InlineKeyboardButton("Sell & Manage", callback_data='position'),
        types.InlineKeyboardButton("Community", url='https://t.me/resistanceCatTon'),
        types.InlineKeyboardButton("Bridge", callback_data='bridge'),
        types.InlineKeyboardButton("Wallets", callback_data='wallets'),
        types.InlineKeyboardButton("Referrals", callback_data='referrals'),
        types.InlineKeyboardButton("Docs", url='https://reca.live/docs'),
        types.InlineKeyboardButton("Refresh", callback_data='refreshhh'),
        types.InlineKeyboardButton("Limit Order", callback_data='limit_order')
    ]

    markup.row(buttons[0], buttons[1], buttons[2])
    markup.row(buttons[3])
    markup.row(buttons[4], buttons[5])
    markup.row(buttons[6], buttons[7])
    markup.row(buttons[8])

    if save_new_user(user_id, referral_id, inviter_referral_id):
        increment_referral_count(inviter_referral_id)  # Increment the count for the inviter
        mention = user_info.username if user_info.username else user_info.first_name

        user_wallet = get_wallet_address(user_id)

        if user_wallet:
            user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
            user_balance_tons = user_balance / 10**9
        else:
            user_balance_tons = 0  # Default to 0 if no wallet found

        user_balance_tons = math.floor(user_balance_tons * 100) / 100

        if user_balance_tons == 0:
            balance_text = "You currently have no TON in your wallet. Deposit some ton or use our bridge function from the commands"
        else:
            balance_text = f"You currently have <code>{user_balance_tons:.2f}</code> TON in your wallet"

        default_wallet = get_default_wallet(user_id)

        if default_wallet:
            default_address_text = f"<code>{user_wallet}</code> <i>(Tap to copy)</i>"
        else:
            default_address_text = "You currently have no Active wallet /create_wallet or /import_wallet"

        welcome_message = (
            f"<u><b>Welcome to ResistanceBot</b></u>\n\n"
            f"TONs fastest bot to trade any jetton!\n\n"
            f"{balance_text}\n\n"
            f"{default_address_text}\n\n"
            f"Refer your friends to earn <b>20%</b> of their fee indefinitely\n\n"
            f"For more info on your wallet and to retrieve your private key, tap the wallet button below. User funds are safe on our Bot, but if you expose your private key we can't protect you!\n\n"
            f"<a href='https://www.geckoterminal.com/ton/pools/EQC5_Js0m5eO2BF4gAppApvOao9idv7uDALfHDfbMDO67b9Y'>Chart</a> | "
            f"<a href='https://www.coingecko.com/en/coins/the-resistance-cat'>Coingecko</a> | "
            f"<a href='https://t.me/WalletTrackerTon_bot'>Wallet Tracker</a>"
        )

        photo_url = 'https://i.ibb.co/2NZwqM7/IMG-6107.jpg'

        sent_message = bot.send_photo(user_id, photo_url, welcome_message, reply_markup=markup, parse_mode="HTML")
        last_messages[user_id] = [sent_message.message_id]
    else:
        send_message_and_record(user_id, "There was a problem registering your account.")

def save_new_user(user_id, referral_id, inviter_referral_id=None):
    cursor = get_cursor()
    try:
        query = """
        INSERT INTO user_referrals (user_id, referral_id, inviter_referral_id, total_referrals, referral_balance)
        VALUES (%s, %s, %s, 0, 0)
        """
        cursor.execute(query, (user_id, referral_id, inviter_referral_id))
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Failed to insert new user: {err}")
        return False
    finally:
        cursor.close()

async def update_referral_balance(user_id, referral_bonus):
    cursor = get_cursor()
    try:
        # Fetch the inviter_referral_id for the current user
        cursor.execute("SELECT inviter_referral_id FROM user_referrals WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        inviter_referral_id = result[0] if result else None

        if inviter_referral_id:
            # Update the inviter's referral balance
            cursor.execute("""
                UPDATE user_referrals
                SET referral_balance = referral_balance + %s
                WHERE referral_id = %s
            """, (referral_bonus, inviter_referral_id))
            db.commit()
    except Exception as e:
        print(f"Failed to update referral balance: {e}")
        db.rollback()
    finally:
        cursor.close()

def create_user_positions_table():
    cursor = get_cursor()
    create_table_query = """
    CREATE TABLE IF NOT EXISTS user_positions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        token_name VARCHAR(255) NOT NULL,
        token_symbol VARCHAR(50) NOT NULL,
        contract_address VARCHAR(255) NOT NULL,
        initial_price DECIMAL(18, 8) NOT NULL,
        amount_received DECIMAL(18, 8) NOT NULL,
        ton_amount DECIMAL(18, 8) NOT NULL,
        buy_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user (user_id),
        INDEX idx_contract (contract_address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cursor.execute(create_table_query)
    db.commit()
    cursor.close()

# Call the function to ensure the table is created
create_user_positions_table()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    parts = message.text.split()
    inviter_referral_id = parts[1] if len(parts) > 1 else DEFAULT_INVITER_REFERRAL_ID  # Extract the inviter's referral ID

    markup = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton("Buy", callback_data='buy_button'),
        types.InlineKeyboardButton("Sell & Manage", callback_data='position'),
        types.InlineKeyboardButton("Community", url='https://t.me/resistanceCatTon'),
        types.InlineKeyboardButton("Bridge", callback_data='bridge'),
        types.InlineKeyboardButton("Wallets", callback_data='wallets'),
        types.InlineKeyboardButton("Referrals", callback_data='referrals'),
        types.InlineKeyboardButton("Docs", url='https://reca.live/docs'),
        types.InlineKeyboardButton("Refresh", callback_data='refreshhh'),
        types.InlineKeyboardButton("Limit Order", callback_data='limit_order')
    ]

    markup.row(buttons[0], buttons[1], buttons[2])
    markup.row(buttons[3])
    markup.row(buttons[4], buttons[5])
    markup.row(buttons[6], buttons[7])
    markup.row(buttons[8])

    user_info = bot.get_chat(user_id)  # Fetch user info to get the username
    mention = f"@{user_info.username}" if user_info.username else user_info.first_name

    user_wallet = get_wallet_address(user_id)

    if user_wallet:
        user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
        user_balance_tons = user_balance / 10**9
    else:
        user_balance_tons = 0  # Default to 0 if no wallet found

    user_balance_tons = math.floor(user_balance_tons * 100) / 100

    if user_balance_tons == 0:
        balance_text = "You currently have no TON in your wallet. Deposit some ton or use our bridge function from the commands"
    else:
        balance_text = f"You currently have <code>{user_balance_tons:.2f}</code> TON in your wallet"

    default_wallet = get_default_wallet(user_id)

    if default_wallet:
        default_address_text = f"<code>{user_wallet}</code> <i>(Tap to copy)</i>"
    else:
        default_address_text = "You currently have no Active wallet /create_wallet or /import_wallet"

    if user_is_new(user_id):
        handle_new_user(user_id, inviter_referral_id)
    else:
        welcome_message = (
            f"<u><b>Welcome to ResistanceBot</b></u>\n\n"
            f"TONs fastest bot to trade any jetton!\n\n"
            f"{balance_text}\n\n"
            f"{default_address_text}\n\n"
            f"Refer your friends to earn <b>20%</b> of their fee indefinitely\n\n"
            f"For more info on your wallet and to retrieve your private key, tap the wallet button below. User funds are safe on our Bot, but if you expose your private key we can't protect you!\n\n"
            f"<a href='https://www.geckoterminal.com/ton/pools/EQC5_Js0m5eO2BF4gAppApvOao9idv7uDALfHDfbMDO67b9Y'>Chart</a> | "
            f"<a href='https://www.coingecko.com/en/coins/the-resistance-cat'>Coingecko</a> | "
            f"<a href='https://t.me/WalletTrackerTon_bot'>Wallet Tracker</a>"
        )

        photo_url = 'https://i.ibb.co/2NZwqM7/IMG-6107.jpg'

        sent_message = send_message_and_record(user_id, welcome_message, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        last_messages[user_id] = [sent_message.message_id]

def send_welcome_button(user_id):

    markup = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton("Buy", callback_data='buy_button'),
        types.InlineKeyboardButton("Sell & Manage", callback_data='position'),
        types.InlineKeyboardButton("Community", url='https://t.me/resistanceCatTon'),
        types.InlineKeyboardButton("Bridge", callback_data='bridge'),
        types.InlineKeyboardButton("Wallets", callback_data='wallets'),
        types.InlineKeyboardButton("Referrals", callback_data='referrals'),
        types.InlineKeyboardButton("Docs", url='https://reca.live/docs'),
        types.InlineKeyboardButton("Refresh", callback_data='refreshhh'),
        types.InlineKeyboardButton("Limit Order", callback_data='limit_order')
    ]

    markup.row(buttons[0], buttons[1], buttons[2])
    markup.row(buttons[3])
    markup.row(buttons[4], buttons[5])
    markup.row(buttons[6], buttons[7])
    markup.row(buttons[8])

    user_info = bot.get_chat(user_id)  # Fetch user info to get the username
    mention = f"@{user_info.username}" if user_info.username else user_info.first_name

    user_wallet = get_wallet_address(user_id)

    if user_wallet:
        user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
        user_balance_tons = user_balance / 10**9
    else:
        user_balance_tons = 0  # Default to 0 if no wallet found

    user_balance_tons = math.floor(user_balance_tons * 100) / 100

    if user_balance_tons == 0:
        balance_text = "You currently have no TON in your wallet. Deposit some ton or use our bridge function from the commands"
    else:
        balance_text = f"You currently have <code>{user_balance_tons:.2f}</code> TON in your wallet"

    default_wallet = get_default_wallet(user_id)

    if default_wallet:
        default_address_text = f"<code>{user_wallet}</code> <i>(Tap to copy)</i>"
    else:
        default_address_text = "You currently have no Active wallet /create_wallet or /import_wallet"

    welcome_message = (
        f"<u><b>Welcome to ResistanceBot</b></u>\n\n"
        f"TONs fastest bot to trade any jetton!\n\n"
        f"{balance_text}\n\n"
        f"{default_address_text}\n\n"
        f"Refer your friends to earn <b>20%</b> of their fee indefinitely\n\n"
        f"To get started with trading, create a new wallet here or import your existing wallet\n\n"
        f"<a href='https://www.geckoterminal.com/ton/pools/EQC5_Js0m5eO2BF4gAppApvOao9idv7uDALfHDfbMDO67b9Y'>Chart</a> | "
        f"<a href='https://www.coingecko.com/en/coins/the-resistance-cat'>Coingecko</a> | "
        f"<a href='https://t.me/WalletTrackerTon_bot'>Wallet Tracker</a>"
    )

    photo_url = 'https://i.ibb.co/2NZwqM7/IMG-6107.jpg'

    edit_last_message(user_id, welcome_message, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)

def show_main_menu(user_id):
    # Prepare and send the main menu buttons to the user
    markup = types.InlineKeyboardMarkup()
    create_wallet_button = types.InlineKeyboardButton("💳 Create Wallet", callback_data='create_new_wallet')
    import_wallet_button = types.InlineKeyboardButton("💳 Import Wallet", callback_data='import_wallet')
    wallets_button = types.InlineKeyboardButton("Wallets 💼", callback_data='wallets')
    community_button = types.InlineKeyboardButton("Join Community 💬", url='https://t.me/resistanceCatTon')
    referrals_button = types.InlineKeyboardButton("Refer Friends 👥", callback_data='referrals')
    buys_button = types.InlineKeyboardButton("Buy 🛒", callback_data='buy_button')
    manual_button = types.InlineKeyboardButton("User Manual 📝", callback_data='manual')
    skip_button = types.InlineKeyboardButton("Bridge 🔁", callback_data='bridge')
    limit_order_button = types.InlineKeyboardButton("Limit Order ⏳", callback_data='limit_order')
    markup.add(create_wallet_button, import_wallet_button)
    markup.add(wallets_button, community_button)
    markup.add(referrals_button, buys_button)
    markup.add(manual_button, skip_button)
    markup.add(limit_order_button)

    # Send the message and store the message ID for reference
    sent_message = send_message_and_record(user_id, "Choose an option:", reply_markup=markup)
    sent_buttons[user_id] = (sent_message.message_id,)  # Store as a tuple

@bot.callback_query_handler(func=lambda call: call.data == 'send_to_all')
def handle_send_to_all(call):
    try:
        user_id = call.message.chat.id
        if user_id not in user_data:
            user_data[user_id] = {}  # Initialize if not already present
        user_data[user_id]['state'] = 'AWAITING_HEADLINE_ALL'

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_transaction"))
        send_new_message_and_delete_last(user_id, "Please enter the message headline:", reply_markup=markup)
    except Exception as e:
        print(f"Error in handle_send_to_all: {e}")
        send_message_and_record(user_id, "An error occurred. Please try again.")
        handle_skip_now(user_id)
        return

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'AWAITING_HEADLINE_ALL')
def handle_headline_input(message):
    user_id = message.chat.id
    user_data[user_id]['headline'] = message.text
    user_data[user_id]['state'] = 'AWAITING_MESSAGE_ALL'

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⏪️ Back", callback_data="back_to_headline"))
    markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_transaction"))
    send_new_message_and_delete_last(user_id, "Now enter the main message:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'AWAITING_MESSAGE_ALL')
def handle_message_input(message):
    user_id = message.chat.id
    user_data[user_id]['main_message'] = message.text  # Store the main message
    user_data[user_id]['state'] = 'AWAITING_PHOTO_ALL'  # Update the state

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Skip Photo", callback_data="skip_photo_all"))
    send_new_message_and_delete_last(user_id, "You can upload a photo or skip this step:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'AWAITING_PHOTO_ALL', content_types=['photo'])
def handle_photo_input_all(message):
    user_id = message.chat.id
    user_data[user_id]['photo'] = message.photo[-1].file_id  # Store the photo file ID
    user_data[user_id]['state'] = 'AWAITING_VIDEO_ALL'  # Update the state

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Skip Video", callback_data="skip_video_all"))
    send_new_message_and_delete_last(user_id, "You can now upload a video or skip this step:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'skip_photo_all')
def handle_skip_photo_all(call):
    user_id = call.message.chat.id
    user_data[user_id]['photo'] = None  # No photo provided
    user_data[user_id]['state'] = 'AWAITING_VIDEO_ALL'

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Skip Video", callback_data="skip_video_all"))
    send_new_message_and_delete_last(user_id, "You can now upload a video or skip this step:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'AWAITING_VIDEO_ALL', content_types=['video'])
def handle_video_input_all(message):
    user_id = message.chat.id
    user_data[user_id]['video'] = message.video.file_id
    user_data[user_id]['state'] = 'AWAITING_LINK_ALL'

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Skip Link", callback_data="skip_link_all"))
    send_new_message_and_delete_last(user_id, "You can now enter a link or skip this step:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'skip_video_all')
def handle_skip_video_all(call):
    user_id = call.message.chat.id
    user_data[user_id]['video'] = None
    user_data[user_id]['state'] = 'AWAITING_LINK_ALL'

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Skip Link", callback_data="skip_link_all"))
    send_new_message_and_delete_last(user_id, "You can now enter a link or skip this step:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'AWAITING_LINK_ALL')
def handle_link_input_all(message):
    user_id = message.chat.id
    user_data[user_id]['link'] = message.text  # Store the link
    user_data[user_id]['state'] = 'READY_TO_SUBMIT_ALL'  # Update the state

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Submit", callback_data="submit_message_all"))
    markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_transaction"))
    send_new_message_and_delete_last(user_id, "You can submit your message or cancel:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'skip_link_all')
def handle_skip_link_all(call):
    user_id = call.message.chat.id
    user_data[user_id]['link'] = None  # No link provided
    user_data[user_id]['state'] = 'READY_TO_SUBMIT_ALL'

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Submit", callback_data="submit_message_all"))
    markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_transaction"))
    send_new_message_and_delete_last(user_id, "You can submit your message or cancel:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "submit_message_all")
def handle_submit_message(call):
    user_id = call.message.chat.id
    send_new_message_and_delete_last(user_id, "🔁 _sending to all users_", parse_mode='Markdown')

    # Ensure the user is in the correct state to submit
    if user_data[user_id].get('state') != 'READY_TO_SUBMIT_ALL':
        send_message_and_record(user_id, "Please complete all required steps before submitting your message.")
        return

    # Extract the components of the message
    headline = user_data[user_id].get('headline', '')
    main_message = user_data[user_id].get('main_message', '')
    photo_content = user_data[user_id].get('photo', None)
    video_content = user_data[user_id].get('video', None)
    link_content = user_data[user_id].get('link', '')

    # Check for the presence of at least a headline and a main message
    if headline and main_message:
        thread = threading.Thread(target=broadcast_message, args=(user_id, headline, main_message, photo_content, link_content, video_content))
        thread.start()
        send_message_and_record(user_id, "Message ✅ sent to all users.")

        # Reset the user's state and clear their data for a new interaction
        user_data[user_id] = {}
        handle_skip_now(user_id)
    else:
        send_message_and_record(user_id, "Error: Missing headline or main message. Please try again.")
        handle_skip_now(user_id)

def broadcast_message(user_id, headline, text_content, photo_content, link_content, video_content):
    user_ids = get_all_user_ids()
    for recipient_id in user_ids:
        try:
            # Construct the message content based on the presence of link_content
            if link_content:
                message_content = f"*{headline}*\n\n{text_content}\n\n{link_content}"
            else:
                message_content = f"*{headline}*\n\n{text_content}"

            # Send photo if exists
            if photo_content:
                bot.send_photo(recipient_id, photo_content, caption=message_content, parse_mode='Markdown')
            # Send video if exists
            elif video_content:
                bot.send_video(recipient_id, video_content, caption=message_content, parse_mode='Markdown')
            # Send headline and text message
            else:
                send_message_and_record(recipient_id, message_content, parse_mode='Markdown')

            time.sleep(5)  # Adjust the delay as needed

        except telebot.apihelper.ApiException as e:
            if e.error_code == 429:
                retry_after = e.result_json['parameters']['retry_after']
                print(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
                # Retry sending all contents
                try:
                    if link_content:
                        message_content = f"*{headline}*\n\n{text_content}\n\n{link_content}"
                    else:
                        message_content = f"*{headline}*\n\n{text_content}"

                    if photo_content:
                        bot.send_photo(recipient_id, photo_content, caption=message_content, parse_mode='Markdown')
                    elif video_content:
                        bot.send_video(recipient_id, video_content, caption=message_content, parse_mode='Markdown')
                    else:
                        send_message_and_record(recipient_id, message_content, parse_mode='Markdown')
                except Exception as retry_exception:
                    print(f"Failed to retry sending message to {recipient_id}: {retry_exception}")
            elif e.error_code == 403 and "bot was blocked by the user" in str(e):
                print(f"Skipping user {recipient_id} because the bot was blocked.")
            else:
                print(f"Failed to send message to {recipient_id}: {e}")

def show_pairs(user_id):
    # Create the markup for the pairs
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for pair in pairs:
        button = types.InlineKeyboardButton(pair["pair"], callback_data=f"pair_{pair['pair']}")
        buttons.append(button)

    # Add buttons to the markup in pairs
    for i in range(0, len(buttons), 2):
        if i+1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])

    # Add a back button
    back_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_menu')
    markup.add(back_button)

    send_new_message_and_delete_last(user_id, "Select a pair:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_order_'))
def handle_cancel_order(call):
    user_id = call.message.chat.id

    # Delete all position-related messages
    if user_id in user_sessions and 'position_messages' in user_sessions[user_id]:
        while user_sessions[user_id]['position_messages']:
            message_id = user_sessions[user_id]['position_messages'].pop()
            try:
                delete_message(user_id, message_id)
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code == 400 and 'message to delete not found' in e.description:
                    pass  # Ignore this specific error
                else:
                    print(f"Failed to delete message {message_id}: {e}")

    try:
        order_id = int(call.data.split('_')[2])
        cancel_order(order_id)
        send_message_and_record(user_id, f"✅ *Order {order_id} has been cancelled.*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Failed to cancel order {order_id} for user {user_id}: {e}")
        send_message_and_record(user_id, f"❌ *Failed to cancel order {order_id}. Please try again later.*", parse_mode='Markdown')

def cancel_order(order_id):
    try:
        cursor = get_cursor()
        cursor.execute('''
        UPDATE orders
        SET status = 'cancelled'
        WHERE id = %s
        ''', (order_id,))
        db.commit()
        cursor.close()
    except Exception as e:
        logging.error(f"Failed to cancel order {order_id}: {e}")

def handle_bridge(user_id):
    if user_id in last_messages:
        message_id = last_messages[user_id][-1]  # Get the last message_id
        show_pairs_button(user_id, message_id)

def show_pairs_button(user_id, message_id):
    try:

        # Create the markup for the pairs
        pairs_markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = []
        for pair in pairs:
            button = types.InlineKeyboardButton(pair["pair"], callback_data=f"pair_{pair['pair']}")
            buttons.append(button)

        # Add buttons to the markup in pairs
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                pairs_markup.add(buttons[i], buttons[i + 1])
            else:
                pairs_markup.add(buttons[i])

        # Add a back button
        back_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_menu')
        pairs_markup.add(back_button)

        bot.edit_message_reply_markup(chat_id=user_id, message_id=message_id, reply_markup=pairs_markup)
    except Exception as e:
        print(f"Error in show_pairs_button: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pair_"))
def handle_pair_selection(call):
    user_id = call.message.chat.id
    selected_pair = call.data.split("pair_")[1]

    # Initialize the user state
    if user_id not in user_data:
        user_data[user_id] = {}

    # Find the pair details
    for pair in pairs:
        if pair["pair"] == selected_pair:
            user_data[user_id]['pair'] = pair
            break

    user_data[user_id]['step'] = 'amount'

    pair_details = user_data[user_id]['pair']

    # Ask for the amount
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_menu')
    markup.add(back_button)
    send_new_message_and_delete_last(user_id, f"Please enter the amount of {pair_details['from_currency'].upper()} you want to bridge", reply_markup=markup)

@bot.message_handler(func=lambda message: message.chat.id in user_data and user_data[message.chat.id].get('step') == 'amount')
def ask_for_receiver_address(message):
    user_id = message.chat.id
    if message.text == "🔙 Back to Menu":
        show_pairs(user_id)
        return

    amount = message.text

    pair_details = user_data[user_id]['pair']

    # Update the user state with the amount
    user_data[user_id]['amount'] = amount
    user_data[user_id]['step'] = 'receiver_address'

    # Ask for the receiver address
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_menu')
    markup.add(back_button)
    send_new_message_and_delete_last(user_id, f"Please enter the receiver address ( {pair_details['to_currency'].upper()} Wallet )", reply_markup=markup)

@bot.message_handler(func=lambda message: message.chat.id in user_data and user_data[message.chat.id].get('step') == 'receiver_address')
def confirm_transaction(message):
    user_id = message.chat.id

    try:
        if message.text == "🔙 Back to Menu":
            show_pairs(user_id)
            return

        receiver_address = message.text

        # Update the user state with the receiver address
        user_data[user_id]['receiver_address'] = receiver_address

        # Retrieve the transaction details
        pair_details = user_data[user_id]['pair']
        amount = user_data[user_id]['amount']

        # Call the create_exchange function
        result = create_exchange(
            user_id,
            pair_details['to_currency'],
            amount,
            receiver_address,
            pair_details['to_network'],
            pair_details['from_currency'],
            pair_details['from_network']
        )

        if result:
            response_text = (
                f"🔄 <b>Exchange Created Successfully!</b>\n\n"
                f"<u><b>Transaction Details:</b></u>\n\n"
                f"📤 <b>From Currency:</b> {pair_details['from_currency'].upper()}\n"
                f"📥 <b>To Currency:</b> {pair_details['to_currency'].upper()}\n"
                f"💰 <b>Amount to Pay:</b> <code>{amount}</code> {pair_details['from_currency'].upper()}\n\n"
                f"📨 <b>Receiver Address:</b> <code>{receiver_address}</code>\n"
                f"🔗 <b>Paying {pair_details['from_currency'].upper()} To:</b> <code>{result['payinAddress']}</code>\n\n"
                f"💵 <b>Amount to Receive:</b> <code>{result['toAmount']}</code> {pair_details['to_currency'].upper()}\n"
                f"🏷️ <b>Transaction ID:</b> <code>{result['id']}</code>"
            )

            # Create the confirmation markup
            markup = types.InlineKeyboardMarkup()
            confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data=f'confirm_transaction_{result["id"]}')
            cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
            markup.add(confirm_button, cancel_button)

            send_message_and_record(user_id, response_text, parse_mode="HTML")
            send_new_message_and_delete_last(user_id, f'Please send <b>{amount}</b> {pair_details["from_currency"].upper()} to <code>{result["payinAddress"]}</code> and click "Confirm" to initiate the bridging process.', reply_markup=markup, parse_mode="HTML")
        else:
            return

    except KeyError as e:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        return
    except Exception as e:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        return

def finalize_transaction(call, transaction_id):
    user_id = call.message.chat.id

    try:
        send_message_and_record(user_id, '✅ _bridging submitted. this may take up to 10mins to be processed_', parse_mode="Markdown")

        # Retrieve the transaction details
        pair_details = user_data[user_id]['pair']
        amount = user_data[user_id]['amount']
        receiver_address = user_data[user_id]['receiver_address']

        # Start a thread to monitor the transaction
        thread = threading.Thread(target=monitor_transaction, args=(user_id, transaction_id))
        thread.start()

        # Clear the user state after processing the transaction
        del user_data[user_id]
        handle_skip_now(user_id)

    except KeyError as e:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
    except Exception as e:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_transaction_'))
def handle_confirm_transaction(call):
    transaction_id = call.data.split('_')[-1]
    finalize_transaction(call, transaction_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('trade_buy_') or call.data.startswith('trade_sell_') or call.data.startswith('trade_enter_'))
def handle_trade_buttons(call):
    user_id = call.message.chat.id
    data = call.data

    if data.startswith('trade_buy_'):
        ton_amt = data.split('_')[2]
        user_sessions[user_id]['ton_amt'] = ton_amt
    elif data.startswith('trade_sell_'):
        sell_pct = data.split('_')[2]
        user_sessions[user_id]['sell_pct'] = sell_pct
    # Regenerate the markup with updated values
    markup = generate_markup(user_id)
    bot.edit_message_reply_markup(chat_id=user_id, message_id=call.message.message_id, reply_markup=markup)

def monitor_transaction(user_id, transaction_id):
    api_key = 'b122ed0f04f27d76cf9a6ed0d38f62e04d685752fb2736731731f43bd483551e'
    url = f'https://api.changenow.io/v2/exchange/by-id?id={transaction_id}'

    headers = {
        'x-changenow-api-key': api_key
    }

    start_time = time.time()
    max_duration = 2 * 60 * 60  # 2 hours in seconds

    while True:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result['status'] == 'finished':
                    send_message_and_record(user_id, f"🎉 <b>Transaction Completed!</b>\n"
                                              f"💵 <b>Amount Received:</b> <code>{result['toAmount']}</code> {result['toCurrency'].upper()}\n"
                                              f"🏷️ <b>Transaction ID:</b> <code>{result['id']}</code>", parse_mode="HTML")
                    break
                elif result['status'] == 'failed':
                    send_message_and_record(user_id, f"❌ <b>Transaction Failed!</b>\n"
                                              f"🏷️ <b>Transaction ID:</b> <code>{result['id']}</code>\n"
                                              f"❗ <b>Reason:</b> {result['error']['message']}", parse_mode="HTML")
                    break
            elif response.status_code == 502:
                print("502 Bad Gateway error encountered. Retrying...")
            else:
                print(f"Unexpected status code {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

        # Check if the maximum duration has been exceeded
        if time.time() - start_time > max_duration:
            send_message_and_record(user_id, "⚠️ <b>Transaction Monitoring Timeout</b>\n"
                                      f"Transaction ID: <code>{transaction_id}</code>\n"
                                      "⏰ <b>Monitoring stopped after 2 hours.</b>", parse_mode="HTML")
            break

        time.sleep(30)  # Wait for 30 seconds before retrying

@bot.message_handler(func=lambda message: True)  # Handles all messages
def handle_new_message(message):
    """
    Handles new messages and checks if the message contains a jetton contract address.
    If it does, calls the handle_jettons_contract function.
    """
    user_id = message.chat.id
    text = message.text.strip()

    # Delete all position-related messages
    if user_id in user_sessions and 'position_messages' in user_sessions[user_id]:
        while user_sessions[user_id]['position_messages']:
            message_id = user_sessions[user_id]['position_messages'].pop()
            try:
                delete_message(user_id, message_id)
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code == 400 and 'message to delete not found' in e.description:
                    pass  # Ignore this specific error
                else:
                    print(f"Failed to delete message {message_id}: {e}")

    if text == '/create_wallet':
        create_new_wallet(message)
    elif text == '/import_wallet':
        import_wallet(message)
    elif text == '/trade':
        send_message_and_record(user_id, "*Paste the CA of Jetton you would like to buy / sell.*", parse_mode="Markdown")
    elif text == '/referrals':
        handle_referral_info(user_id)
    elif text == '/transfer':
        start_transfer_message(message)
    elif text == '/positions':
        handle_position(user_id)
    elif text == '/bridge':
        show_pairs(user_id)
    else:
        handle_jettons_contract(user_id, text)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data.split(":")
    action = data[0]

    # Delete all position-related messages
    if user_id in user_sessions and 'position_messages' in user_sessions[user_id]:
        while user_sessions[user_id]['position_messages']:
            message_id = user_sessions[user_id]['position_messages'].pop()
            try:
                delete_message(user_id, message_id)
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code == 400 and 'message to delete not found' in e.description:
                    pass  # Ignore this specific error
                else:
                    print(f"Failed to delete message {message_id}: {e}")


    if call.data == 'create_new_wallet':
        create_new_wallet(call.message)
    elif call.data == 'import_wallet':
        import_wallet(call.message)
    elif call.data == 'show_balances':
        show_wallets_balance(call.message)
    elif call.data == 'skip':
        handle_skip(call)
    elif call.data == 'refresh':
        handle_skip(call)
    elif call.data == 'select_dedust':
        handle_platform_selection(call)
    elif call.data == 'select_stonfi':
        handle_platform_selection(call)
    elif call.data == 'select_swap':
        handle_action_selection(call)
    elif call.data == 'select_limit':
        handle_action_selection(call)
    elif call.data == 'select_buy':
        handle_buy_sell_selection(call)
    elif call.data == 'select_sell':
        handle_buy_sell_selection(call)
    elif call.data == 'select_price':
        handle_indicator_selection(call)
    elif call.data == 'select_change':
        handle_indicator_selection(call)
    elif call.data == 'select_mcap':
        handle_indicator_selection(call)
    elif call.data == 'enter_exp':
        handle_exp_selection(call)
    elif call.data == 'enter_buy_amt':
        send_message_and_record(user_id, "Please enter the TON amount to buy:")
        bot.register_next_step_handler_by_chat_id(user_id, handle_enter_buy_amt)
    elif call.data == 'enter_sell_amt':
        send_message_and_record(user_id, "Please enter the percentage (1-100) to sell:")
        bot.register_next_step_handler_by_chat_id(user_id, handle_enter_sell_amt)
    elif call.data == 'enter_indicator':
        indicator = user_sessions[user_id].get('indicator', 'mcap')
        if indicator == 'price':
            send_message_and_record(user_id, "Please enter the price (e.g., 0.00347)")
        elif indicator == 'change':
            send_message_and_record(user_id, "Please enter the percentage change (e.g., 5, 10, -5):")
        elif indicator == 'mcap':
            send_message_and_record(user_id, "Please enter the market cap (e.g., 157.43k or 5.34m):")
        bot.register_next_step_handler_by_chat_id(user_id, handle_enter_indicator)
    elif call.data == 'create_order':
        handle_create_order(user_id)
    elif call.data == 'limit_order':
        handle_limit_order(call)
    elif call.data == 'trade_buy_':
        handle_trade_buttons(call)
    elif call.data == 'trade_sell_':
        handle_trade_buttons(call)
    elif call.data == 'referrals':
        handle_referral_info_button(chat_id)
    elif call.data == 'refreshhh':
        send_welcome_button(chat_id)
    elif call.data == 'bridge':
        handle_bridge(chat_id)
    elif call.data == 'back_to_menu':
        send_welcome_button(chat_id)
    elif call.data == 'wallets':
        show_wallets_button(call.message)
    elif call.data == 'delete_default_wallet':
        delete_default_wallet(call)
    elif call.data.startswith('select_wallet:'):
        show_wallet_options(call)
    elif call.data == 'transfer':
        start_transfer_message(call.message)
    elif call.data == 'transfer_jetton':
        handle_transfer_jetton(call)
    elif call.data == 'confirm_transfer_jetton':
        confirm_transfer_jetton(call)
    elif call.data == 'buy':
        handle_buy(call)
    elif call.data == 'buy_button':
        markup = types.InlineKeyboardMarkup()
        back_button = types.InlineKeyboardButton("Close", callback_data='refreshhh')
        markup.add(back_button)
        send_new_message_and_delete_last(user_id, "*Enter the token contract address to start trading*", reply_markup=markup, parse_mode="Markdown")
    elif call.data.startswith('confirm_sell_'):
        confirm_sell_now(call)
    elif call.data == 'position':
        handle_position(user_id)
    elif call.data == 'withdraw_bonus':
        handle_withdraw_bonus(call)
    elif call.data == 'confirm_buy':
        confirm_buy(call)
    elif call.data == 'export':
        export_connected_wallet(call)
    elif call.data == 'sell':
        sell_jetton(call)
    elif call.data.startswith('sell_'):
        sell_percentage(call)
    elif call.data.startswith('buy_'):
        ask_buy_amount_direct(call)
    elif call.data == 'confirm_sell':
        confirm_sell(call)
    elif call.data == 'cancel_transaction':
        handle_cancel(call)
    elif call.data == 'confirm_transaction':
        process_transaction(call)
    elif call.data == 'back_to_previous':
        handle_back(call)
    elif call.data == "submit_message":
        handle_submit_message(call)
    elif call.data == 'send_to_all':
        handle_send_to_all(call)
    elif call.data == "back_to_headline":
        # Reset to headline input state
        user_data[user_id]['state'] = 'AWAITING_HEADLINE'
        send_new_message_and_delete_last(user_id, "Please enter the message headline again:")
    elif call.data == "back_to_message":
        # Reset to message input state
        user_data[user_id]['state'] = 'AWAITING_MESSAGE'
        send_new_message_and_delete_last(user_id, "Please enter the main message again:")
    if action == 'set_default':
        wallet_name = data[1]
        set_default_wallet(user_id, wallet_name)
        # Define the markup for the response message
        markup = types.InlineKeyboardMarkup()
        # Add any buttons you need to the markup here
        send_new_message_and_delete_last(user_id, f'✅_Wallet_ *{wallet_name}* _has been set as default Wallet_', reply_markup=markup, parse_mode="Markdown")

    elif action == 'delete_wallet':
        wallet_name = data[1]
        delete_wallet(user_id, wallet_name)  # Assuming you have a function to delete a specific wallet
        # Define the markup for the response message

async def close_all(self):
    for peer in self._peers:
        self._check_errors(peer)
        if peer.inited:
            await peer.close()
    if self._checker is not None:  # Check if _checker is not None
        self._checker.cancel()
        while not self._checker.done():
            await asyncio.sleep(0)
    self.inited = False

async def initialize_wallet_if_needed(user_id, status, user_balance):
    if status != 'active' and user_balance > 0:
        try:
            mnemonic = get_user_mnemonic(user_id)
            # Initialize the LiteBalancer with mainnet configuration
            balancer = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
            await balancer.start_up()  # Properly start the balancer

            # Initialize the WalletV4R2
            wallet = await WalletV4R2.from_mnemonic(balancer, mnemonic)
            await wallet.send_init_external()
        except Exception as e:
            print(f"Error during wallet initialization: {e}")
        finally:
            await balancer.close_all()

def handle_skip(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_data[user_id] = {}

    wallet_address = get_wallet_address(user_id)

    user_balance = 0

    if wallet_address:
        user_balance, status = asyncio.run(fetch_ton_balance(wallet_address))
        user_balance_tons = user_balance / 10**9  # Convert to TONs
    else:
        user_balance_tons = 0  # Default to 0 if no wallet found
        status = 'unknown'

    user_balance_tons = math.floor(user_balance_tons * 100) / 100

    # Show account status in the message
    if status != 'active':
        account_status_message = f"Your wallet status is *{status}*\n\n⚠️ *Fund Your Wallet and Refresh*\nWait for *3mins to 10mins* for your wallet to be *Active*"
    else:
        account_status_message = f"Your wallet status is *{status}*"

    user_wallet = get_wallet_address(user_id)

    if user_wallet:
        user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
        user_balance_tons = user_balance / 10**9
    else:
        user_balance_tons = 0  # Default to 0 if no wallet found

    user_balance_tons = math.floor(user_balance_tons * 100) / 100

    if user_balance_tons == 0:
        balance_text = "You currently have no TON in your wallet. Deposit some ton or use our bridge function from the commands"
    else:
        balance_text = f"You currently have <code>{user_balance_tons:.2f}</code> TON in your wallet"

    default_wallet = get_default_wallet(user_id)

    if default_wallet:
        default_address_text = f"<code>{user_wallet}</code> <i>(Tap to copy)</i>"
    else:
        default_address_text = "You currently have no Active wallet /create_wallet or /import_wallet"

    welcome_message = (
        f"<u><b>Welcome to ResistanceBot</b></u>\n\n"
        f"TONs fastest bot to trade any jetton!\n\n"
        f"{balance_text}\n\n"
        f"{default_address_text}\n\n"
        f"Refer your friends to earn <b>20%</b> of their fee indefinitely\n\n"
        f"To get started with trading, create a new wallet here or import your existing wallet\n\n"
        f"<a href='https://www.geckoterminal.com/ton/pools/EQC5_Js0m5eO2BF4gAppApvOao9idv7uDALfHDfbMDO67b9Y'>Chart</a> | "
        f"<a href='https://www.coingecko.com/en/coins/the-resistance-cat'>Coingecko</a> | "
        f"<a href='https://t.me/WalletTrackerTon_bot'>Wallet Tracker</a>"
    )

    asyncio.run(initialize_wallet_if_needed(user_id, status, user_balance))

    # Fetch referral balance from the database
    referral_balance = get_referral_balance(user_id)

    # Format the balance message to include both TON and referral balances
    balance_message = f"Your TON Balance is *{user_balance_tons:.2f}* TONs 💎\n\nYour Referral Balance is *{referral_balance:.2f}* TONs 💎\n\n{account_status_message}"

    markup = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton("Buy", callback_data='buy_button'),
        types.InlineKeyboardButton("Sell & Manage", callback_data='position'),
        types.InlineKeyboardButton("Community", url='https://t.me/resistanceCatTon'),
        types.InlineKeyboardButton("Bridge", callback_data='bridge'),
        types.InlineKeyboardButton("Wallets", callback_data='wallets'),
        types.InlineKeyboardButton("Referrals", callback_data='referrals'),
        types.InlineKeyboardButton("Docs", url='https://reca.live/docs'),
        types.InlineKeyboardButton("Refresh", callback_data='refreshhh'),
        types.InlineKeyboardButton("Limit Order", callback_data='limit_order')
    ]

    markup.row(buttons[0], buttons[1], buttons[2])
    markup.row(buttons[3])
    markup.row(buttons[4], buttons[5])
    markup.row(buttons[6], buttons[7])
    markup.row(buttons[8])
    # Check if user is an admin
    if is_user_admin(user_id):
        # Add 'Send to All' and 'Send to User' buttons for admins
        markup.add(types.InlineKeyboardButton('📣 Send to All', callback_data='send_to_all'))

    # Send new message and update the storage.
    send_message_and_record(chat_id, welcome_message, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)

def handle_skip_now(user_id):
    wallet_address = get_wallet_address(user_id)
    user_data[user_id] = {}

    user_balance = 0

    if wallet_address:
        user_balance, status = asyncio.run(fetch_ton_balance(wallet_address))
        user_balance_tons = user_balance / 10**9  # Convert to TONs
    else:
        user_balance_tons = 0  # Default to 0 if no wallet found
        status = 'unknown'

    user_balance_tons = math.floor(user_balance_tons * 100) / 100

    # Show account status in the message
    if status != 'active':
        account_status_message = f"Your wallet status is *{status}*\n\n⚠️ *Fund Your Wallet and Refresh*\nWait for *3mins to 10mins* for your wallet to be *Active*"
    else:
        account_status_message = f"Your wallet status is *{status}*"

    user_wallet = get_wallet_address(user_id)

    if user_wallet:
        user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
        user_balance_tons = user_balance / 10**9
    else:
        user_balance_tons = 0  # Default to 0 if no wallet found

    user_balance_tons = math.floor(user_balance_tons * 100) / 100

    if user_balance_tons == 0:
        balance_text = "You currently have no TON in your wallet. Deposit some ton or use our bridge function from the commands"
    else:
        balance_text = f"You currently have <code>{user_balance_tons:.2f}</code> TON in your wallet"

    default_wallet = get_default_wallet(user_id)

    if default_wallet:
        default_address_text = f"<code>{user_wallet}</code> <i>(Tap to copy)</i>"
    else:
        default_address_text = "You currently have no Active wallet /create_wallet or /import_wallet"

    welcome_message = (
        f"<u><b>Welcome to ResistanceBot</b></u>\n\n"
        f"TONs fastest bot to trade any jetton!\n\n"
        f"{balance_text}\n\n"
        f"{default_address_text}\n\n"
        f"Refer your friends to earn <b>20%</b> of their fee indefinitely\n\n"
        f"To get started with trading, create a new wallet here or import your existing wallet\n\n"
        f"<a href='https://www.geckoterminal.com/ton/pools/EQC5_Js0m5eO2BF4gAppApvOao9idv7uDALfHDfbMDO67b9Y'>Chart</a> | "
        f"<a href='https://www.coingecko.com/en/coins/the-resistance-cat'>Coingecko</a> | "
        f"<a href='https://t.me/WalletTrackerTon_bot'>Wallet Tracker</a>"
    )

    asyncio.run(initialize_wallet_if_needed(user_id, status, user_balance))

    # Fetch referral balance from the database
    referral_balance = get_referral_balance(user_id)

    # Format the balance message to include both TON and referral balances
    balance_message = f"Your TON Balance is *{user_balance_tons:.2f}* TONs 💎\n\nYour Referral Balance is *{referral_balance:.2f}* TONs 💎\n\n{account_status_message}"

    markup = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton("Buy", callback_data='buy_button'),
        types.InlineKeyboardButton("Sell & Manage", callback_data='position'),
        types.InlineKeyboardButton("Community", url='https://t.me/resistanceCatTon'),
        types.InlineKeyboardButton("Bridge", callback_data='bridge'),
        types.InlineKeyboardButton("Wallets", callback_data='wallets'),
        types.InlineKeyboardButton("Referrals", callback_data='referrals'),
        types.InlineKeyboardButton("Docs", url='https://reca.live/docs'),
        types.InlineKeyboardButton("Refresh", callback_data='refreshhh'),
        types.InlineKeyboardButton("Limit Order", callback_data='limit_order')
    ]

    markup.row(buttons[0], buttons[1], buttons[2])
    markup.row(buttons[3])
    markup.row(buttons[4], buttons[5])
    markup.row(buttons[6], buttons[7])
    markup.row(buttons[8])

    # Check if user is an admin
    if is_user_admin(user_id):
        # Add 'Send to All' and 'Send to User' buttons for admins
        markup.add(types.InlineKeyboardButton('📣 Send to All', callback_data='send_to_all'))

    # Send new message and update the storage.
    send_message_and_record(user_id, welcome_message, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)

async def handle_skip_now_now(user_id):
    wallet_address = get_wallet_address(user_id)
    user_data[user_id] = {}

    user_balance = 0

    if wallet_address:
        user_balance, status = await fetch_ton_balance(wallet_address)
        user_balance_tons = user_balance / 10**9  # Convert to TONs
    else:
        user_balance_tons = 0  # Default to 0 if no wallet found
        status = 'unknown'

    user_balance_tons = math.floor(user_balance_tons * 100) / 100

    # Show account status in the message
    if status != 'active':
        account_status_message = f"Your wallet status is *{status}*\n\n⚠️ *Fund Your Wallet and Refresh*\nWait for *3mins to 10mins* for your wallet to be *Active*"
    else:
        account_status_message = f"Your wallet status is *{status}*"

    user_wallet = get_wallet_address(user_id)

    if user_wallet:
        user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
        user_balance_tons = user_balance / 10**9
    else:
        user_balance_tons = 0  # Default to 0 if no wallet found

    user_balance_tons = math.floor(user_balance_tons * 100) / 100

    if user_balance_tons == 0:
        balance_text = "You currently have no TON in your wallet. Deposit some ton or use our bridge function from the commands"
    else:
        balance_text = f"You currently have <code>{user_balance_tons:.2f}</code> TON in your wallet"

    default_wallet = get_default_wallet(user_id)

    if default_wallet:
        default_address_text = f"<code>{user_wallet}</code> <i>(Tap to copy)</i>"
    else:
        default_address_text = "You currently have no Active wallet /create_wallet or /import_wallet"

    welcome_message = (
        f"<u><b>Welcome to ResistanceBot</b></u>\n\n"
        f"TONs fastest bot to trade any jetton!\n\n"
        f"{balance_text}\n\n"
        f"{default_address_text}\n\n"
        f"Refer your friends to earn <b>20%</b> of their fee indefinitely\n\n"
        f"To get started with trading, create a new wallet here or import your existing wallet\n\n"
        f"<a href='https://www.geckoterminal.com/ton/pools/EQC5_Js0m5eO2BF4gAppApvOao9idv7uDALfHDfbMDO67b9Y'>Chart</a> | "
        f"<a href='https://www.coingecko.com/en/coins/the-resistance-cat'>Coingecko</a> | "
        f"<a href='https://t.me/WalletTrackerTon_bot'>Wallet Tracker</a>"
    )


    await initialize_wallet_if_needed(user_id, status, user_balance)

    # Fetch referral balance from the database
    referral_balance = get_referral_balance(user_id)

    # Format the balance message to include both TON and referral balances
    balance_message = f"Your TON Balance is *{user_balance_tons:.2f}* TONs 💎\n\nYour Referral Balance is *{referral_balance:.2f}* TONs 💎\n\n{account_status_message}"

    markup = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton("Buy", callback_data='buy_button'),
        types.InlineKeyboardButton("Sell & Manage", callback_data='position'),
        types.InlineKeyboardButton("Community", url='https://t.me/resistanceCatTon'),
        types.InlineKeyboardButton("Bridge", callback_data='bridge'),
        types.InlineKeyboardButton("Wallets", callback_data='wallets'),
        types.InlineKeyboardButton("Referrals", callback_data='referrals'),
        types.InlineKeyboardButton("Docs", url='https://reca.live/docs'),
        types.InlineKeyboardButton("Refresh", callback_data='refreshhh'),
        types.InlineKeyboardButton("Limit Order", callback_data='limit_order')
    ]

    markup.row(buttons[0], buttons[1], buttons[2])
    markup.row(buttons[3])
    markup.row(buttons[4], buttons[5])
    markup.row(buttons[6], buttons[7])
    markup.row(buttons[8])

    # Check if user is an admin
    if is_user_admin(user_id):
        # Add 'Send to All' and 'Send to User' buttons for admins
        markup.add(types.InlineKeyboardButton('📣 Send to All', callback_data='send_to_all'))

    # Send new message and update the storage.
    send_message_and_record(user_id, welcome_message, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


def get_referral_balance(user_id):
    cursor = get_cursor(dictionary=True)
    try:
        cursor.execute("SELECT referral_balance FROM user_referrals WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        if result:
            return float(result['referral_balance'])
        return 0.0
    finally:
        cursor.close()

def handle_referral_info(user_id):
    referral_data = get_user_referral_data(user_id)
    # Prepare the markup for the "Back" button and "Withdraw Bonus" button
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text="🔙 Back", callback_data='back_to_menu')
    withdraw_button = types.InlineKeyboardButton(text="💸 Transfer Bonus", callback_data='withdraw_bonus')
    markup.add(withdraw_button, back_button)
    photo_url = 'https://i.ibb.co/LCcfHGp/IMG-6965.jpg'

    if referral_data:
        referral_balance, total_referrals, referral_link = referral_data
        info_message = (f"🔄 *Your Referral Info:*\n\n"
                        f"👥 Total Referrals: *{total_referrals}*\n\n"
                        f"💰 Referral Balance: *{format_price(referral_balance)}* TONs 💎\n\n"
                        f"🔗 Your Referral Link: `{referral_link}`\n\n"
                        f"💰 *Earn passive income for your lifetime with our referral program.*\n\n"
                        f"😻 Refer your friends and earn 20% of their fees  indefinitely, highest referal rewards among all other trading bots.")
        send_new_message_and_delete_last(user_id, info_message, reply_markup=markup, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        send_new_message_and_delete_last(user_id, "🚫 You do not have any referrals yet. Share your referral link to start earning!", reply_markup=markup)

def handle_referral_info_button(user_id):
    referral_data = get_user_referral_data(user_id)
    # Prepare the markup for the "Back" button and "Withdraw Bonus" button
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text="🔙 Back", callback_data='back_to_menu')
    withdraw_button = types.InlineKeyboardButton(text="💸 Transfer Bonus", callback_data='withdraw_bonus')
    markup.add(withdraw_button, back_button)
    photo_url = 'https://i.ibb.co/LCcfHGp/IMG-6965.jpg'

    if referral_data:
        referral_balance, total_referrals, referral_link = referral_data
        info_message = (f"🔄 *Your Referral Info:*\n\n"
                        f"👥 Total Referrals: *{total_referrals}*\n\n"
                        f"💰 Referral Balance: *{format_price(referral_balance)}* TONs 💎\n\n"
                        f"🔗 Your Referral Link: `{referral_link}`\n\n"
                        f"💰 *Earn passive income for your lifetime with our referral program.*\n\n"
                        f"😻 Refer your friends and earn 20% of their fees  indefinitely, highest referal rewards among all other trading bots.")
        edit_last_message(user_id, info_message, reply_markup=markup, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        send_new_message_and_delete_last(user_id, "🚫 You do not have any referrals yet. Share your referral link to start earning!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'withdraw_bonus')
def handle_withdraw_bonus(call):
    user_id = call.message.chat.id
    referral_data = get_user_referral_data(user_id)

    if referral_data:
        referral_balance, _, _ = referral_data
        if referral_balance > 1:
            # Transfer the referral balance to the user's wallet
            user_wallet_address = get_wallet_address(user_id)
            default_wallet_mnemonics = [
                "situate", "slow", "inhale", "idea", "barrel", "sound",
                "ketchup", "over", "tone", "genius", "few", "shield",
                "habit", "enough", "vapor", "deposit", "nose", "fault",
                "father", "secret", "above", "oblige", "coil", "icon"
            ]

            asyncio.run(transfer_referral_bonus(user_id, user_wallet_address, referral_balance, default_wallet_mnemonics))
        else:
            send_message_and_record(user_id, "🚫 You cannot withdraw less than 1 TONs 💎.")
            handle_skip(call)
    else:
        send_message_and_record(user_id, "🚫 You do not have any referral bonus to withdraw.")
        handle_skip(call)

async def transfer_referral_bonus(user_id, user_wallet_address, referral_balance, mnemonics):
    try:
        send_new_message_and_delete_last(user_id, f"💸 _Sending Referral TONs 💎..._", parse_mode='Markdown')
        provider = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await provider.start_up()
        wallet = await WalletV4R2.from_mnemonic(provider=provider, mnemonics=mnemonics.split())

        # Transfer the referral balance to the user's wallet
        transfer_amount_nano = int(referral_balance * 10**9)
        await wallet.transfer(destination=Address(user_wallet_address), amount=transfer_amount_nano, body=Cell.empty())

        # Update the referral balance in the database
        cursor = get_cursor()
        try:
            cursor.execute("UPDATE user_referrals SET referral_balance = 0 WHERE user_id = %s", (user_id,))
            db.commit()
        finally:
            cursor.close()

        await provider.close_all()

        send_message_and_record(user_id, f"✅ Successfully withdrawn *{format_price(referral_balance)}* TONs 💎 to your wallet.")
        await handle_skip_now_now(user_id)
    except Exception as e:
        send_message_and_record(user_id, f"❌ An error occurred during the withdrawal: ```{e}```", parse_mode='Markdown')
        await handle_skip_now_now(user_id)


def get_user_referral_data(user_id):
    cursor = get_cursor(dictionary=True)
    try:
        cursor.execute("SELECT referral_balance, total_referrals, referral_id FROM user_referrals WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        if result:
            referral_balance = float(result['referral_balance'])
            total_referrals = int(result['total_referrals'])
            referral_id = result['referral_id']
            referral_link = f"https://t.me/RecaTradingBot?start={referral_id}"
            return referral_balance, total_referrals, referral_link
        return None
    finally:
        cursor.close()

def delete_message(chat_id, message_id):
    """
    Deletes a message.

    :param chat_id: The chat ID where the message is located.
    :param message_id: The ID of the message to delete.
    """
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"Failed to delete message: {e}")

def edit_last_message(user_id, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
    """
    Edits the last message sent to the user.

    :param user_id: The user ID to whom the message was sent.
    :param text: The new text to update the message with.
    :param reply_markup: The new inline keyboard markup.
    :param parse_mode: The parse mode for the message.
    :param disable_web_page_preview: Disable link previews for links in this message.
    """
    if user_id in last_messages and last_messages[user_id]:
        try:
            last_message_id = last_messages[user_id][-1]
            # Edit the last message
            edited_message = bot.edit_message_text(
                text,
                user_id,
                last_message_id,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
            # Record the ID of the edited message in a new list
            last_messages[user_id] = [edited_message.message_id]
        except Exception as e:
            print(f"Failed to edit message: {e}")

def send_new_message_and_edit_last(user_id, text, reply_markup=None, parse_mode=None, photo_url=None, disable_web_page_preview=None):
    """
    Edits the last message immediately or sends a new message if no previous message exists.

    :param user_id: The user ID to whom the message is sent.
    :param text: The text of the new message.
    :param reply_markup: The inline keyboard markup for the new message.
    :param parse_mode: The parse mode for the message.
    :param photo_url: URL of the photo to send along with the message.
    """
    sent_message = None  # Initialize sent_message to None
    if photo_url:
        # Send a new photo message if photo_url is provided
        sent_message = bot.send_photo(user_id, photo_url, caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        # Edit the last message if it exists, otherwise send a new message
        if user_id in last_messages and last_messages[user_id]:
            edit_last_message(user_id, text, reply_markup, parse_mode)
        else:
            sent_message = send_message_and_record(user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
            last_messages.setdefault(user_id, []).append(sent_message.message_id)
    return sent_message

def send_message_and_record(user_id, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
    """
    Sends a new message and records the message ID.

    :param user_id: The user ID to whom the message is sent.
    :param text: The text of the message to be sent.
    :param reply_markup: The inline keyboard markup.
    :param parse_mode: The parse mode for the message.
    :param disable_web_page_preview: Disable link previews for links in this message.
    """
    sent_message = bot.send_message(user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
    last_messages[user_id] = [sent_message.message_id]
    return sent_message

def send_new_message_and_delete_last_buttons(user_id, text, reply_markup=None, parse_mode=None, photo_url=None, disable_web_page_preview=None):
    """ Deletes the last message immediately and sends a new message. """
    if user_id in last_messages and last_messages[user_id]:
        delete_message(user_id, last_messages[user_id].pop())

    sent_message = send_message_and_record(user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)

    if photo_url:
        bot.send_photo(user_id, photo_url, caption=text)

    last_messages.setdefault(user_id, []).append(sent_message.message_id)
    return sent_message

def send_new_message_and_delete_last(user_id, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
    """ Deletes the last message immediately and sends a new message. """
    if user_id in last_messages and last_messages[user_id]:
        delete_message(user_id, last_messages[user_id].pop())
    sent_message = send_message_and_record(user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
    last_messages.setdefault(user_id, []).append(sent_message.message_id)
    return sent_message

def send_new_message_and_delete_last_2(user_id, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
    """ Keeps the last 2 messages and starts deleting from the third message onwards. """
    if user_id in last_messages and len(last_messages[user_id]) >= 2:
        delete_message(user_id, last_messages[user_id].pop(0))  # delete the oldest message

    sent_message = send_message_and_record(user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
    last_messages.setdefault(user_id, []).append(sent_message.message_id)
    return sent_message

def send_new_message_and_delete_last_3(user_id, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
    """ Keeps the last 3 messages and starts deleting from the third message onwards. """
    if user_id in last_messages and len(last_messages[user_id]) >= 3:
        delete_message(user_id, last_messages[user_id].pop(0))  # delete the oldest message

    sent_message = send_message_and_record(user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
    last_messages.setdefault(user_id, []).append(sent_message.message_id)
    return sent_message

@bot.message_handler(func=lambda message: message.text == '💳 Create Wallet')
def create_new_wallet(message):
    user_id = message.chat.id

    user_wallet_creation_status[user_id] = True

    # Create menu options for the user.
    markup = types.InlineKeyboardMarkup(row_width=2)
    cancel_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_menu')
    markup.add(cancel_button)

    sent_message = send_new_message_and_delete_last(user_id, '✏️ _Enter Your Wallet Name:_', reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(sent_message, create_wallet_name)

def create_wallet_name(message):
    asyncio.run(handle_create_wallet(message))

async def handle_create_wallet(message):
    user_id = message.chat.id
    wallet_name = message.text.strip()

    if len(wallet_name) > 10:
        send_message_and_record(user_id, '⚠️ The wallet name cannot exceed 10 characters.')
        return

    try:

        provider = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await provider.start_up()

        cursor = get_cursor()

        try:
            cursor.execute("SELECT 1 FROM user_wallets WHERE user_id = %s AND wallet_name = %s", (user_id, wallet_name))
            if cursor.fetchone():
                send_message_and_record(user_id, f'⚠️ A wallet with the name "{wallet_name}" already exists.')
                return
        finally:
            cursor.close()

        client = TonlibClient()
        TonlibClient.enable_unaudited_binaries() # Assuming this is synchronous
        await client.init_tonlib()  # Ensure this is actually asynchronous

        wallet = await client.create_wallet()
        if not wallet:
            raise ValueError("Failed to create wallet")

        seed = await wallet.export()
        if not seed:
            raise ValueError("Failed to export seed")

        mnemonics = seed

        wallet = await WalletV4R2.from_mnemonic(provider=provider, mnemonics=mnemonics.split())

        wallet_address = wallet.address  # Convert to string to avoid issues

        # Address formatting (assuming the method to_str exists)
        bounceable_address = wallet_address.to_str(is_user_friendly=True, is_bounceable=True, is_url_safe=True, is_test_only=False)
        non_bounceable_address = wallet_address.to_str(is_user_friendly=True, is_bounceable=False, is_url_safe=True, is_test_only=False)

        insert_wallet_data(user_id, wallet_name, wallet_address, bounceable_address, non_bounceable_address, seed)

        send_message_and_record(
            user_id,
            (
                f'🆕 New Wallet "<b>{wallet_name}</b>" Created! 🎉\n\n'
                f'✏️ Address:\n<pre>{non_bounceable_address}</pre>\n\n'
                f'<b>Seed:</b>\n<pre>{seed}</pre>\n\n'
                f'⚠️ Keep your seed safe!'
            ),
            parse_mode='HTML'
        )
        set_default_wallet(user_id, wallet_name)
        await handle_skip_now_now(user_id)

    except Exception as e:
        print(f"An error occurred please try again: {e}")
        await handle_skip_now_now(user_id)
    finally:
        await provider.close_all()

@bot.message_handler(func=lambda message: message.text == '💳 Add Wallet')
def import_wallet(message):
    user_id = message.chat.id

    user_wallet_creation_status[user_id] = True

    # Create menu options for the user.
    markup = types.InlineKeyboardMarkup(row_width=2)
    cancel_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_menu')
    markup.add(cancel_button)

    sent_message = send_new_message_and_delete_last(user_id, '✏️ _Enter Your Wallet Name:_', reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(sent_message, import_wallet_name)

def import_wallet_name(message):
    user_id = message.chat.id
    wallet_name = message.text

    # Check if the user has cancelled the wallet creation process
    if not user_wallet_creation_status.get(user_id, False):
        return  # Exit the function if the user has cancelled

    # Create menu options for the user.
    markup = types.InlineKeyboardMarkup(row_width=2)
    cancel_button = types.InlineKeyboardButton("🔙 Back", callback_data='return')
    markup.add(cancel_button)

    cursor = get_cursor()

    try:
        cursor.execute("SELECT 1 FROM user_wallets WHERE user_id = %s AND wallet_name = %s", (user_id, wallet_name))
        if cursor.fetchone():
            send_message_and_record(user_id, f'⚠️ A wallet with the name "{wallet_name}" already exists.')
            return
    finally:
        cursor.close()

    if len(wallet_name) > 10:
        send_new_message_and_delete_last(user_id, '⚠️ The wallet name cannot exceed 10 characters.')
        return


    else:
        send_new_message_and_delete_last(user_id, '✏️ _Seed Phrase_:', reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(message, import_wallet_private_key, wallet_name)

def import_wallet_private_key(message, wallet_name):
    asyncio.run(handle_import_wallet(message, wallet_name))

async def handle_import_wallet(message, wallet_name):
    user_id = message.chat.id
    seed = message.text.strip()

    if len(wallet_name) > 10:
        send_message_and_record(user_id, '⚠️ The wallet name cannot exceed 10 characters.')
        return

    cursor = get_cursor()

    cursor.execute("SELECT 1 FROM user_wallets WHERE user_id = %s AND wallet_name = %s", (user_id, wallet_name))
    if cursor.fetchone():
        send_message_and_record(user_id, f'⚠️ A wallet with the name "{wallet_name}" already exists.')
        cursor.close()
        return

    cursor.close()

    try:
        mnemonics = seed

        provider = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await provider.start_up()
        wallet = await WalletV4R2.from_mnemonic(provider=provider, mnemonics=mnemonics.split())

        wallet_address = wallet.address  # Convert to string to avoid issues

        # Address formatting (assuming the method to_str exists)
        bounceable_address = wallet_address.to_str(is_user_friendly=True, is_bounceable=True, is_url_safe=True, is_test_only=False)
        non_bounceable_address = wallet_address.to_str(is_user_friendly=True, is_bounceable=False, is_url_safe=True, is_test_only=False)

        insert_wallet_data(user_id, wallet_name, wallet_address, bounceable_address, non_bounceable_address, seed)

        send_message_and_record(
            user_id,
            (
                f'👜 Wallet "<b>{wallet_name}</b>" Imported! 🎉\n\n'
                f'✏️ Address:\n<pre>{non_bounceable_address}</pre>\n\n'
            ),
            parse_mode='HTML'
        )
        set_default_wallet(user_id, wallet_name)
        await handle_skip_now_now(user_id)

    except Exception as e:
        print(f"An error occurred please try again: {e}")
        await handle_skip_now_now(user_id)
    finally:
        await provider.close_all()

def get_wallet_address(user_id):
    cursor = get_cursor(dictionary=True)
    try:
        # Fetch the address of the default wallet
        cursor.execute("""
            SELECT non_bounceable_address
            FROM user_wallets
            WHERE user_id = %s AND is_default = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        result = cursor.fetchone()
        # If no default is set, you might still want to return the most recent wallet
        if not result:
            cursor.execute("""
                SELECT non_bounceable_address
                FROM user_wallets
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            result = cursor.fetchone()

        return result['non_bounceable_address'] if result else None
    finally:
        cursor.close()

def get_user_mnemonic(user_id):
    cursor = get_cursor(dictionary=True)
    try:
        # Fetch the address of the default wallet
        cursor.execute("""
            SELECT seed
            FROM user_wallets
            WHERE user_id = %s AND is_default = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        result = cursor.fetchone()
        # If no default is set, you might still want to return the most recent wallet
        if not result:
            cursor.execute("""
                SELECT seed
                FROM user_wallets
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            result = cursor.fetchone()

        return result['seed'] if result else None
    finally:
        cursor.close()

def insert_wallet_data(user_id, wallet_name, wallet_address, bounceable_address, non_bounceable_address, seed):
    # Ensure database connection is active
    cursor = get_cursor()

    try:
        # Convert Address objects or any complex types to strings
        wallet_address_str = str(wallet_address)
        bounceable_address_str = str(bounceable_address)
        non_bounceable_address_str = str(non_bounceable_address)

        # SQL query to insert data
        query = """
        INSERT INTO user_wallets (user_id, wallet_name, wallet_address, bounceable_address, non_bounceable_address, seed)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        # Execute the SQL command
        cursor.execute(query, (user_id, wallet_name, wallet_address_str, bounceable_address_str, non_bounceable_address_str, seed))

        # Commit the transaction
        db.commit()

    except Exception as e:
        # Rollback in case there is any error
        db.rollback()
        print(f"Failed to insert wallet data: {e}")

    finally:
        # Close cursor and free resources
        cursor.close()

def export_connected_wallet(call):
    user_id = call.message.chat.id

    try:
        # Get a fresh cursor
        cursor = get_cursor()

        # Fetch the default wallet details for the user from the database
        cursor.execute("SELECT wallet_name, wallet_address, bounceable_address, non_bounceable_address, seed FROM user_wallets WHERE user_id = %s AND is_default = TRUE", (user_id,))
        default_wallet = cursor.fetchone()

        if default_wallet:
            wallet_info = (
                f"📝 Wallet Name: {default_wallet[0]}\n\n"
                f"⚡️ Bounceable Address: {default_wallet[2]}\n\n"
                f"⚡️ Non-Bounceable Address: {default_wallet[3]}\n\n"
                f"⚠️ Seed: {default_wallet[4]}"
            )

            # Create a temporary file and write wallet details to it
            file_path = f"{user_id}_{default_wallet[0]}_wallet.txt"
            with open(file_path, "w") as file:
                file.write(wallet_info)

            # Send the file to the user
            with open(file_path, "rb") as file:
                bot.send_document(user_id, file)
                show_wallets(call.message)

            # Remove the temporary file after sending
            os.remove(file_path)

            bot.answer_callback_query(call.id, 'Connected wallet exported successfully!')
        else:
            bot.answer_callback_query(call.id, 'No connected wallet found to export.')

    except Exception as e:
        send_message_and_record(user_id, 'An error occurred while exporting your connected wallet. Please try again later.')
        print(f"Error exporting connected wallet: {e}")  # Log the exception for debugging
    finally:
        cursor.close()  # Close the cursor after using it


def send_back_button(chat_id, text, markup=None):
    if markup is None:
        markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_previous')
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
    markup.add(back_button, cancel_button)
    send_new_message_and_delete_last(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_previous')
def handle_back(call):
    chat_id = call.message.chat.id
    current_stage = user_wallet_creation_status.get(chat_id, {}).get('stage')

    if current_stage == 'ask_for_destination':
        # If user is at the destination stage, go back to amount input
        user_wallet_creation_status[chat_id]['stage'] = 'ask_for_amount'
        send_back_button(chat_id, "Please enter the amount you would like to transfer:")
    elif current_stage == 'ask_for_comment':
        # If user is at the comment stage, go back to destination input
        user_wallet_creation_status[chat_id]['stage'] = 'ask_for_destination'
        send_back_button(chat_id, "Enter the destination address:")

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_transaction')
def handle_cancel(call):
    chat_id = call.message.chat.id
    if chat_id in user_wallet_creation_status:
        del user_wallet_creation_status[chat_id]
    handle_skip(call)


@bot.callback_query_handler(func=lambda call: call.data == 'transfer')
def start_transfer(message):
    chat_id = message.chat.id
    start_transfer_message(message)

def start_transfer_message(message):
    user_id = message.chat.id
    user_wallet_creation_status[user_id] = {'stage': 'ask_for_amount'}
    send_back_button(user_id, "Please enter the amount you would like to transfer:")
    bot.register_next_step_handler(message, ask_for_destination)

def ask_for_destination(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("🚫 Close", callback_data='cancel_transaction')
    markup.add(cancel_button)
    try:
        amount = float(message.text)  # Convert to float for comparison
    except ValueError:
        send_message_and_record(chat_id, "Invalid amount. Please Retry.")
        return

    wallet_address = get_wallet_address(chat_id)

    if wallet_address:
        user_balance, status = asyncio.run(fetch_ton_balance(wallet_address))  # Assume balance is fetched in nanograms
        user_balance_tons = user_balance / 10**9
    else:
        user_balance = 0  # Default to 0 if no wallet found

    user_balance_tons = math.floor(user_balance_tons * 1000) / 1000

    if user_balance_tons < amount:
        send_message_and_record(chat_id, f"⚠️ Insufficient balance. Your balance is *{user_balance_tons:.3f}* TONs 💎, but you tried to send *{amount}* TONs 💎.", reply_markup=markup, parse_mode='Markdown')
        return

    user_wallet_creation_status[chat_id]['amount'] = amount
    user_wallet_creation_status[chat_id]['stage'] = 'ask_for_destination'

    send_new_message_and_delete_last(chat_id, "Enter the destination address:")
    bot.register_next_step_handler(message, handle_transfer)

@bot.message_handler(func=lambda message: user_wallet_creation_status.get(message.chat.id, {}).get('stage') == 'ask_for_destination')
def handle_transfer(message):
    chat_id = message.chat.id
    destination = message.text.strip()
    user_wallet_creation_status[chat_id]['destination'] = destination
    user_wallet_creation_status[chat_id]['stage'] = 'confirm'

    markup = types.InlineKeyboardMarkup()
    confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data='confirm_transaction')
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
    markup.add(confirm_button, cancel_button)

    amount = user_wallet_creation_status[chat_id]['amount']
    confirmation_text = f"Please confirm the transaction:\n\n💎 Amount: *{amount}* TONs\n\n✏️ Destination: `{destination}`"
    send_new_message_and_delete_last(chat_id, confirmation_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_transaction')
def process_transaction(call):
    chat_id = call.message.chat.id
    # Ensure we retrieve all necessary data
    amount = float(user_wallet_creation_status.get(chat_id, {}).get('amount'))
    destination = user_wallet_creation_status.get(chat_id, {}).get('destination')

    if not amount or not destination:
        send_message_and_record(chat_id, "Error: Missing amount or destination.")
        return

    # Run the async function using asyncio.run
    try:
        asyncio.run(execute_transfer(chat_id, amount, destination))
        handle_skip(call)
    except Exception as e:
        handle_skip(call)

async def execute_transfer(chat_id, amount, recipient_address):
    balancer = None
    try:
        send_new_message_and_delete_last(chat_id, f"💸 _Transferring {amount} TONs 💎..._", parse_mode='Markdown')
        mnemonic = get_user_mnemonic(chat_id)
        # Initialize the LiteBalancer with mainnet configuration
        balancer = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await balancer.start_up()  # Properly start the balancer

        # Initialize the WalletV4R2
        wallet = await WalletV4R2.from_mnemonic(balancer, mnemonic)

        NANOTON = int(1000000000 * amount)  # Convert TON to nanograms

        # Perform the transfer
        await wallet.transfer(destination=Address(recipient_address), amount=NANOTON, body=Cell.empty())
        markup = types.InlineKeyboardMarkup()
        cancel_button = types.InlineKeyboardButton("✅ Done", callback_data='cancel_transaction')
        markup.add(cancel_button)
        send_message_and_record(chat_id, f"Transfer of *{amount}* to `{recipient_address}` was Successfully  Submitted!✅", parse_mode='Markdown')
    except Exception as e:
        send_message_and_record(chat_id, f"‼️ An error occurred please try again: ```{str(e)}```", parse_mode='Markdown')
        print(f"Error occurred: {e}")
    finally:
        if balancer:
            await balancer.close_all()

async def execute_transfer_fee(chat_id, amount, recipient_address):
    balancer = None
    try:
        await asyncio.sleep(50)
        mnemonic = get_user_mnemonic(chat_id)
        # Initialize the LiteBalancer with mainnet configuration
        balancer = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await balancer.start_up()  # Properly start the balancer

        # Initialize the WalletV4R2
        wallet = await WalletV4R2.from_mnemonic(balancer, mnemonic)

        NANOTON = int(1000000000 * amount)  # Convert TON to nanograms

        # Perform the transfer
        await wallet.transfer(destination=Address(recipient_address), amount=NANOTON, body=Cell.empty())
    except Exception as e:
        print(f"Error occurred when sending fee: {e}")
    finally:
        if balancer:
            await balancer.close_all()

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_transaction')
def cancel_transaction(call):
    chat_id = call.message.chat.id
    del user_wallet_creation_status[chat_id]
    handle_skip(call)

# Handle '💼 My Wallets' button
@bot.message_handler(func=lambda message: message.text == '💼 My Wallets')
def show_wallets(message):
    user_id = message.chat.id

    try:
        # Get a fresh cursor
        cursor = get_cursor()

        # Fetch all wallet names for the user from the database
        cursor.execute(f"SELECT wallet_name FROM user_wallets WHERE user_id = %s", (user_id,))
        user_wallets_from_db = cursor.fetchall()

        # Fetch the default wallet for the user from the database
        cursor.execute(f"SELECT wallet_name FROM user_wallets WHERE user_id = %s AND is_default = TRUE", (user_id,))
        default_wallet = cursor.fetchone()

        wallet_list = [wallet[0] for wallet in user_wallets_from_db]  # Extract wallet names from the result

        user_wallet = get_wallet_address(user_id)

        ton_price_usd = fetch_ton_price_usd()

        if user_wallet:
            user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
            user_balance_tons = user_balance / 10**9
        else:
            user_balance_tons = 0  # Default to 0 if no wallet found

        if user_balance_tons > 0:
            balance_usd = user_balance_tons * ton_price_usd
        else:
            balance_usd = 0

        user_balance_tons = math.floor(user_balance_tons * 1000) / 1000

        balance_usd = math.floor(balance_usd * 1000) / 1000

        if default_wallet:
            default_address_text = f"<b>TON·💎</b>\n<code>{user_wallet}</code> <i>(Tap to copy)</i>\nBalance: <code>{user_balance_tons:.2f}</code> TON ( <code>${balance_usd:.2f}</code> )\n\n"
        else:
            default_address_text = ""

        markup = types.InlineKeyboardMarkup(row_width=2)

        for wallet_name in wallet_list:
            select_button = types.InlineKeyboardButton(wallet_name, callback_data=f'select_wallet:{wallet_name}')
            markup.add(select_button)

        # If there's a default wallet, add the delete button
        if default_wallet:
            delete_default_button = types.InlineKeyboardButton('🗑️ Delete', callback_data='delete_default_wallet')
            export_default_button = types.InlineKeyboardButton('⚠️️ Export', callback_data='export')
            markup.row(delete_default_button, export_default_button)
            default_wallet_text = f" (Connected: {default_wallet[0]})"
        else:
            default_wallet_text = ""
        back_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_menu')
        markup.add(back_button)

        send_new_message_and_delete_last(user_id, f'Select or manage your wallets{default_wallet_text}:\n\n{default_address_text}use /create_wallet or /import_wallet to add wallet.', reply_markup=markup, parse_mode="HTML")

        cursor.close()  # Close the cursor after using it
    except Exception as e:
        print('e', e)
        send_message_and_record(user_id, 'An error occurred while fetching your wallets. Please try again later.')

@bot.message_handler(func=lambda message: message.text == '💼 My Wallets')
def show_wallets_button(message):
    user_id = message.chat.id

    try:
        # Get a fresh cursor
        cursor = get_cursor()

        # Fetch all wallet names for the user from the database
        cursor.execute(f"SELECT wallet_name FROM user_wallets WHERE user_id = %s", (user_id,))
        user_wallets_from_db = cursor.fetchall()

        # Fetch the default wallet for the user from the database
        cursor.execute(f"SELECT wallet_name FROM user_wallets WHERE user_id = %s AND is_default = TRUE", (user_id,))
        default_wallet = cursor.fetchone()

        wallet_list = [wallet[0] for wallet in user_wallets_from_db]  # Extract wallet names from the result

        user_wallet = get_wallet_address(user_id)

        ton_price_usd = fetch_ton_price_usd()

        if user_wallet:
            user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
            user_balance_tons = user_balance / 10**9
        else:
            user_balance_tons = 0  # Default to 0 if no wallet found

        if user_balance_tons > 0:
            balance_usd = user_balance_tons * ton_price_usd
        else:
            balance_usd = 0

        user_balance_tons = math.floor(user_balance_tons * 1000) / 1000

        balance_usd = math.floor(balance_usd * 1000) / 1000

        if default_wallet:
            default_address_text = f"<b>TON·💎</b>\n<code>{user_wallet}</code> <i>(Tap to copy)</i>\nBalance: <code>{user_balance_tons:.2f}</code> TON ( <code>${balance_usd:.2f}</code> )\n\n"
        else:
            default_address_text = ""

        markup = types.InlineKeyboardMarkup(row_width=2)

        for wallet_name in wallet_list:
            select_button = types.InlineKeyboardButton(wallet_name, callback_data=f'select_wallet:{wallet_name}')
            markup.add(select_button)

        # If there's a default wallet, add the delete button
        if default_wallet:
            delete_default_button = types.InlineKeyboardButton('🗑️ Delete', callback_data='delete_default_wallet')
            export_default_button = types.InlineKeyboardButton('⚠️️ Export', callback_data='export')
            transfer_button = types.InlineKeyboardButton("Transfer", callback_data='transfer')
            markup.row(delete_default_button, export_default_button)
            markup.row(transfer_button)
            default_wallet_text = f" (Connected: {default_wallet[0]})"
        else:
            default_wallet_text = ""
        back_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_menu')
        markup.add(back_button)

        edit_last_message(user_id, f'Select or manage your wallets{default_wallet_text}:\n\n{default_address_text}use /create_wallet or /import_wallet to add wallet.', reply_markup=markup, parse_mode="HTML")

        cursor.close()  # Close the cursor after using it
    except Exception as e:
        print('e', e)
        send_message_and_record(user_id, 'An error occurred while fetching your wallets. Please try again later.')

@bot.callback_query_handler(func=lambda call: call.data == 'delete_default_wallet')
def delete_default_wallet(call):
    user_id = call.message.chat.id

    try:
        # Get a fresh cursor with dictionary=True to return results as dictionaries
        cursor = get_cursor(dictionary=True)

        # First, find out the default wallet for the user
        cursor.execute("""
            SELECT *
            FROM user_wallets
            WHERE user_id = %s AND is_default = TRUE
        """, (user_id,))
        default_wallet = cursor.fetchone()

        if default_wallet:
            # Delete the default wallet from the original table
            cursor.execute("DELETE FROM user_wallets WHERE user_id = %s AND wallet_name = %s", (user_id, default_wallet['wallet_name']))

            # Commit changes
            db.commit()

            bot.answer_callback_query(call.id, 'Default wallet deleted successfully!')
        else:
            bot.answer_callback_query(call.id, 'No default wallet found to delete.')

    except Exception as e:
        print(f"Error in delete_default_wallet: {e}")
        db.rollback()  # Rollback in case of error
        send_message_and_record(user_id, 'An error occurred while trying to delete your default wallet. Please try again later.')

    finally:
        cursor.close()

    # Redirect the user back to the wallets screen
    show_wallets_button(call.message)

def set_default_wallet(user_id, wallet_name):
    '''Set a wallet as the default for a user.'''
    cursor = get_cursor()

    # Set other wallets to non-default
    cursor.execute("UPDATE user_wallets SET is_default = FALSE WHERE user_id = %s", (user_id,))

    # Set the chosen wallet as default
    cursor.execute("UPDATE user_wallets SET is_default = TRUE WHERE user_id = %s AND wallet_name = %s", (user_id, wallet_name))
    cursor.close()

def get_default_wallet(user_id):
    '''Fetch the default wallet for a user.'''
    cursor = get_cursor()
    cursor.execute("SELECT wallet_name FROM user_wallets WHERE user_id = %s AND is_default = TRUE", (user_id,))
    result = cursor.fetchone()
    cursor.close()

    if result:
        return result[0]
    else:
        return None

def insert_or_update_user_position(user_id, token_name, token_symbol, contract_address, ton_amount, jetton_amount):
    cursor = get_cursor(dictionary=True)
    try:
        # Convert float amounts to Decimal
        ton_amount = Decimal(str(ton_amount))
        jetton_amount = Decimal(str(jetton_amount))

        # Calculate initial price per jetton
        initial_price = ton_amount / jetton_amount
        # Get the current timestamp for buy time
        buy_time = datetime.now()

        # Check if a position with the same token name, symbol, and contract address exists
        cursor.execute("""
            SELECT id, amount_received, ton_amount FROM user_positions
            WHERE user_id = %s AND token_name = %s AND token_symbol = %s AND contract_address = %s
        """, (user_id, token_name, token_symbol, contract_address))
        existing_position = cursor.fetchone()

        if existing_position:
            # Convert existing amounts to Decimal
            existing_amount_received = Decimal(existing_position['amount_received'])
            existing_ton_amount = Decimal(existing_position['ton_amount'])

            # Update the existing position
            new_amount_received = existing_amount_received + jetton_amount
            new_ton_amount = existing_ton_amount + ton_amount
            new_initial_price = new_ton_amount / new_amount_received

            cursor.execute("""
                UPDATE user_positions
                SET initial_price = %s, amount_received = %s, ton_amount = %s, buy_time = %s
                WHERE id = %s
            """, (new_initial_price, new_amount_received, new_ton_amount, buy_time, existing_position['id']))
        else:
            # Insert a new position
            cursor.execute("""
                INSERT INTO user_positions (user_id, token_name, token_symbol, contract_address, initial_price, amount_received, ton_amount, buy_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, token_name, token_symbol, contract_address, initial_price, jetton_amount, ton_amount, buy_time))

        # Commit the transaction
        db.commit()
    except Exception as e:
        print(f"Error inserting or updating user position: {e}")
        db.rollback()
    finally:
        cursor.close()

from decimal import Decimal

def update_user_position_if_needed(user_id, token_symbol, contract_address, current_balance, current_price):
    cursor = get_cursor(dictionary=True)
    try:
        # Fetch the existing position
        cursor.execute("""
            SELECT id, initial_price, amount_received, ton_amount
            FROM user_positions
            WHERE user_id = %s AND token_symbol = %s AND contract_address = %s
        """, (user_id, token_symbol, contract_address))
        position = cursor.fetchone()

        if position:
            current_balance_decimal = Decimal(current_balance)
            current_price_decimal = Decimal(current_price)
            amount_received_decimal = Decimal(position['amount_received'])

            if current_balance_decimal != amount_received_decimal:
                new_amount_received = current_balance_decimal
                new_ton_amount = new_amount_received * current_price_decimal

                if current_balance_decimal > amount_received_decimal:
                    cursor.execute("""
                        UPDATE user_positions
                        SET amount_received = %s, ton_amount = %s, initial_price = %s
                        WHERE id = %s
                    """, (new_amount_received, new_ton_amount, current_price_decimal, position['id']))
                else:
                    cursor.execute("""
                        UPDATE user_positions
                        SET amount_received = %s, ton_amount = %s
                        WHERE id = %s
                    """, (new_amount_received, new_ton_amount, position['id']))

                db.commit()

    except Exception as e:
        print(f"Error updating user position: {e}")
        db.rollback()
    finally:
        cursor.close()

def show_wallet_options(call):
    user_id = call.message.chat.id
    wallet_name = call.data.split(':')[1]  # assuming callback_data is 'select_wallet:<wallet_name>'

    # Create a new cursor for database operations
    cursor = get_cursor()  # Ensure you have this function or replace it with your method of obtaining a fresh cursor

    try:
        # Fetch all wallet names for the user from the database
        cursor.execute("SELECT wallet_name FROM user_wallets WHERE user_id = %s", (user_id,))
        user_wallets_from_db = cursor.fetchall()
        wallet_list = [wallet[0] for wallet in user_wallets_from_db]  # Extract wallet names from the result

        if wallet_name == '🏠 Home':
            default_wallet = get_default_wallet(user_id)
            if default_wallet:
                send_message_and_record(user_id, f'Your default wallet is "{default_wallet}". 🤖')
            else:
                send_message_and_record(user_id, 'You do not have a default wallet set.\n\nplease use /create_wallet or /import_wallet a wallet first')
                return

        elif wallet_name in wallet_list:
            # Begin database transaction
            cursor.execute("BEGIN;")

            # Set this wallet as default for the user in the database
            cursor.execute("UPDATE user_wallets SET is_default = TRUE WHERE user_id = %s AND wallet_name = %s", (user_id, wallet_name))

            # Set other wallets to non-default for this user
            cursor.execute("UPDATE user_wallets SET is_default = FALSE WHERE user_id = %s AND wallet_name != %s", (user_id, wallet_name))

            # Commit database transaction
            cursor.execute("COMMIT;")
            show_wallets_button(call.message)
        else:
            send_message_and_record(user_id, 'Invalid wallet name.')
            show_wallets(call.message)
    except Exception as e:
        # If an error occurs, rollback the database transaction
        cursor.execute("ROLLBACK;")

        # Handle any error that might occur (database errors, unexpected errors, etc.)
        send_message_and_record(user_id, 'An error occurred. Please try again later.')
        print(f"Error in show_wallet_options: {e}")
    finally:
        cursor.close()  # Always close your cursor when done
        return

def show_wallets_balance(message):
    user_id = message.chat.id
    cursor = get_cursor(dictionary=True)
    cursor.execute("SELECT wallet_name, non_bounceable_address FROM user_wallets WHERE user_id = %s", (user_id,))
    wallets = cursor.fetchall()
    cursor.close()

    if not wallets:
        send_message_and_record(user_id, "You don't have any wallets yet.")
        return

    message_text = "*Your Wallets:*\n\n"

    markup = types.InlineKeyboardMarkup(row_width=2)
    cancel_button = types.InlineKeyboardButton("🛖 Home", callback_data='cancel_transaction')
    markup.add(cancel_button)

    for wallet in wallets:
        wallet_name = wallet['wallet_name']
        wallet_address = wallet['non_bounceable_address']

        # Fetching balance

        balance, status = asyncio.run(fetch_ton_balance(wallet_address))
        balance_tons = balance / 10**9
        balance_tons = math.floor(balance_tons * 1000) / 1000

        # Adding wallet info to the message
        message_text += (
                f"🔹 *{wallet_name}*\n\n"
                f"  ✏️ Address: `{wallet_address}`\n\n"
                f"  Balance: `{balance_tons:.3f}` *TONs* 💎\n\n"
                f"  Status: *{status}*\n\n"
            )

        # Add buttons for setting default and deleting the wallet
        markup = types.InlineKeyboardMarkup(row_width=2)
        set_default_button = types.InlineKeyboardButton("✅ Set Default", callback_data=f'set_default:{wallet_name}')
        delete_button = types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_wallet:{wallet_name}')
        cancel_button = types.InlineKeyboardButton("🛖 Home", callback_data='cancel_transaction')
        markup.add(cancel_button)

        send_message_and_record(user_id, message_text, parse_mode='Markdown')
        message_text = ""  # Reset the message text for the next wallet
    send_new_message_and_delete_last(user_id, 'Go to Home 🛖', parse_mode='Markdown', reply_markup=markup)

# Function to handle jettons contract
def download_image(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def format_number(num):
    try:
        num = float(num)
    except ValueError:
        num = 0.0

    if num >= 10**12:
        return "{:.2f}T".format(num / 10**12)
    elif num >= 10**9:
        return "{:.2f}B".format(num / 10**9)
    elif num >= 10**6:
        return "{:.2f}M".format(num / 10**6)
    elif num >= 10**3:
        return "{:.2f}K".format(num / 10**3)
    else:
        # Format the number to 5 decimal places and remove trailing zeros
        formatted_number = "{:.7f}".format(num).rstrip('0').rstrip('.')
        return formatted_number

async def get_jetton_total_supply(jetton_master_address):
    client = None
    try:
        client = LiteBalancer.from_mainnet_config(trust_level=1, timeout=20)
        await client.start_up()

        jetton_master = Address(jetton_master_address)
        method = "get_jetton_data"
        stack = []

        result = await client.run_get_method_local(jetton_master, method, stack)

        if not result or not isinstance(result, list) or len(result) == 0:
            raise ValueError("Invalid response from get_jetton_data method")

        total_supply = result[0]
        return total_supply

    except WalletError as e:
        return None
    except Exception as e:
        return None
    finally:
        if client:
            await client.close_all()

def format_price(price):
    price = float(price)
    if price >= 1:
        price = math.floor(price * 10000) / 10000
        return f"{price:.5f}"
    else:
        decimals = abs(int(f"{price:e}".split('e')[1]))
        return f"{price:.{decimals+3}f}"

def fetch_ton_price_usd():
    url = "https://tonapi.io/v2/rates?tokens=ton&currencies=ton,usd,rub"
    headers = {
        'accept': 'application/json',
        "Authorization": "Bearer AFAIMVWVKVKA55AAAAAM74EW72XURDFL4IDJ2CXK7QIW2AIRC2NSKTWHR5XBDSNB5KHM2DQ"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    if "rates" in data and "TON" in data["rates"] and "prices" in data["rates"]["TON"] and "USD" in data["rates"]["TON"]["prices"]:
        return data["rates"]["TON"]["prices"]["USD"]
    else:
        raise ValueError("TON price not found in TON API response")

def get_jetton_wallet_info(owner_address, jetton_address):
    url = "https://toncenter.com/api/v3/jetton/wallets"

    headers = {
        'X-API-Key': toncenter_api_key
    }

    params = {
        'owner_address': owner_address,
        'jetton_address': jetton_address
    }

    response = requests.get(url, headers=headers, params=params)
    try:
        response_json = response.json()
    except ValueError:
        print(f"Error: Response is not in JSON format: {response.text}")
        return None

    if response.status_code == 200:
        if response_json.get('jetton_wallets'):
            return response_json['jetton_wallets'][0]  # Assuming the first wallet is what you want
        else:
            return None
    else:
        print(f"Error getting jetton wallet info: {response.status_code}, {response_json}")
        return None

def get_jetton_balance(owner_address, jetton_address):
    wallet_info = get_jetton_wallet_info(owner_address, jetton_address)
    if wallet_info:
        return wallet_info.get('balance', '0')  # Default to '0' if balance is not found
    else:
        return '0'

def retry(max_retries=4, delay=1):
    def decorator_retry(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    time.sleep(delay)
                    if retries == max_retries:
                        return None
        return wrapper
    return decorator_retry

@retry(max_retries=4, delay=2)
def get_jetton_total_supply_sync(jetton_contract_address):
    return asyncio.run(get_jetton_total_supply(jetton_contract_address))

def getRequest(address):
    response = requests.get(address)
    response.raise_for_status()
    return response.json()

def getSaat(address):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'}
    response = requests.get(f"https://app.geckoterminal.com/api/p1/ton/pools/{address}" , headers=headers).json()
    print('response', response)
    return response["data"]["attributes"]["price_percent_changes"]["last_1h"]

def getLiquidity(address):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'}
    response = requests.get(f"https://www.geckoterminal.com/ton/pools/{address}", headers=headers)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    div = soup.find("div", {"class": "rounded border border-gray-800 min-w-[20rem] flex-1 p-2 sm:p-4 md:min-w-0 md:flex-none"})
    liquidity_span = div.find('th', text='Liquidity').find_next_sibling('td').find('span')
    return liquidity_span.text

def fetch_pool_data(api_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'}
    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    return response.json()

def fetch_jetton_holders(jetton_contract_address, limit=10, offset=0):
    url = f'https://tonapi.io/v2/jettons/{jetton_contract_address}/holders?limit={limit}&offset={offset}'
    response = requests.get(url, headers={'accept': 'application/json'})
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error fetching jetton holders: {response.status_code}, {response.text}")

def fetch_account_details(account_id):
    url = f'https://tonapi.io/v2/accounts/{account_id}'
    response = requests.get(url, headers={'accept': 'application/json'})
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error fetching account details: {response.status_code}, {response.text}")

def determine_preferred_dex(jetton_contract_address):
    try:
        holders = fetch_jetton_holders(jetton_contract_address)
        for holder in holders['addresses']:
            owner_address = holder['owner']['address']
            if 'STON.fi Dex' in holder['owner'].get('name', ''):
                return 'StonFi'
            else:
                account_details = fetch_account_details(owner_address)
                if 'dedust_vault' in account_details.get('interfaces', []):
                    return 'DeDust'
        return 'Unknown'
    except Exception as e:
        print(f"Error determining preferred DEX: {e}")
        return 'Unknown'

def handle_jettons_contract(user_id, jetton_contract_address):
    try:
        # Fetch metadata
        metadata = fetch_metadata(jetton_contract_address)
        if not validate_metadata(metadata):
            return

        user_balance_tons = 0

        jetton_info = extract_jetton_info(metadata)
        if jetton_info['name'] == 'N/A' and jetton_info['symbol'] == 'N/A':
            return

        # Determine preferred DEX
        preferred_dex = determine_preferred_dex(jetton_contract_address)
        if preferred_dex == 'Unknown':
            send_message_and_record(user_id, "⚠️ Unable to determine the preferred DEX.")
            return

        # Immediately store jetton_info in user_sessions
        user_sessions[user_id] = {
            'jetton_contract_address': jetton_contract_address,
            'name': jetton_info['name'],
            'symbol': jetton_info['symbol'],
            'image_url': jetton_info['image_url'],
            'description': jetton_info['description'],
            'decimals': None,  # Placeholder for now
            'mintable': jetton_info['mintable'],
            'total_supply': jetton_info['total_supply'],
            'balance': None,  # Placeholder for now
            'user_balance': None,  # Placeholder for now
            'pools': None,  # Placeholder for now
            'ton_price_usd': None,  # Placeholder for now
            'price': None,  # Placeholder for now
            'preferred_platform': preferred_dex,  # Default platform based on holders
            'action': 'swap',  # Default action
            'buy_sell': 'buy',  # Default buy/sell
            'indicator': 'mcap',  # Default indicator
            'exp': '1d',  # Default expiration
            'ton_amt': '25',
            'sell_pct': '25'
        }

        send_new_message_and_delete_last(user_id, f"_⚡️ fetching data..._", parse_mode='Markdown')

        # Extract metadata
        jetton_content = metadata.get('result', {}).get('jetton_content', {}).get('data', {})
        decimals = int(jetton_content.get('decimals', 9))

        user_wallet = get_wallet_address(user_id)
        balance_init = get_jetton_balance(user_wallet, jetton_contract_address)
        balance = float(balance_init) / 10**decimals

        ton_price_usd = fetch_ton_price_usd()

        if user_wallet:
            user_balance, status = asyncio.run(fetch_ton_balance(user_wallet))  # Assume balance is fetched in nanograms
            user_balance_tons = user_balance / 10**9
        else:
            user_balance = 0  # Default to 0 if no wallet found

        user_balance_tons = math.floor(user_balance_tons * 1000) / 1000

        # Update the session with decimals, balance, user balance, and ton price
        user_sessions[user_id].update({
            'decimals': decimals,
            'balance': balance,
            'user_balance': user_balance_tons,
            'ton_price_usd': ton_price_usd
        })

        message = prepare_metadata_message(user_id, jetton_info, balance, user_balance_tons, decimals, jetton_contract_address, preferred_dex)

        # Fetch pool ID
        token_info = getRequest(f"https://api.geckoterminal.com/api/v2/networks/ton/tokens/{jetton_contract_address}")
        if 'data' not in token_info:
            send_message_and_record(user_id, "❌ Unable to retrieve pool data.")
            return

        pool_id = token_info["data"]["relationships"]["top_pools"]["data"][0]["id"]
        pool_id = pool_id.replace('ton_', '')

        # Fetch details from the pool
        pool_data_url = f"https://api.geckoterminal.com/api/v2/networks/ton/pools/{pool_id}"
        pool_data = fetch_pool_data(pool_data_url)
        if 'data' not in pool_data:
            send_message_and_record(user_id, "❌ Unable to retrieve detailed pool data.")
            return

        try:
            liquidity = getLiquidity(pool_id.replace('ton_', ''))
        except requests.exceptions.RequestException as e:
            send_message_and_record(user_id, f"Error fetching liquidity data: {e}")
            liquidity = "N/A"

        pool_message = prepare_pool_message_from_api(pool_data, ton_price_usd, jetton_info['symbol'], jetton_info['total_supply'], decimals)

        # Include additional data in the message
        combined_message = message + pool_message['message'] + f"\n💧 Liquidity: {liquidity}"

        # Generate initial markup
        markup = generate_markup(user_id)

        # Send the combined message
        sent_message = send_new_message_and_delete_last(user_id, combined_message, reply_markup=markup, parse_mode='HTML')

        # Store the message ID to use in edit_message_reply_markup
        user_sessions[user_id]['last_message_id'] = sent_message.message_id

        price = fetch_current_price_in_ton(jetton_contract_address)

        # Check if user balance is not the same as amount_received and update if necessary
        update_user_position_if_needed(user_id, jetton_info['symbol'], jetton_contract_address, balance, price)

        # Update session data in the user_sessions dictionary
        user_sessions[user_id].update({
            'price': price
        })

    except requests.exceptions.RequestException as e:
        send_message_and_record(user_id, f"Error: {e}\nDetails: {e.response.text}")  # Print the detailed error message

def generate_markup(user_id):
    action = user_sessions[user_id].get('action', 'swap')
    buy_sell = user_sessions[user_id].get('buy_sell', 'buy')
    exp = user_sessions[user_id].get('exp', '1d')
    indicator = user_sessions[user_id].get('indicator', 'mcap')
    ton_amt = user_sessions[user_id].get('ton_amt', '25')
    sell_pct = user_sessions[user_id].get('sell_pct', '50')
    symbol = user_sessions[user_id].get('symbol', 'TON')
    indicator_value = float(user_sessions[user_id].get(indicator, '0'))

    markup = types.InlineKeyboardMarkup()

    # Trade Buttons
    if action == 'swap':
        trade_buttons = [
            types.InlineKeyboardButton("25 TON", callback_data='buy_25'),
            types.InlineKeyboardButton("50 TON", callback_data='buy_50'),
            types.InlineKeyboardButton("100 TON", callback_data='buy_100'),
            types.InlineKeyboardButton("X TON", callback_data='buy'),
            types.InlineKeyboardButton("Sell 25%", callback_data='sell_25'),
            types.InlineKeyboardButton("Sell 50%", callback_data='sell_50'),
            types.InlineKeyboardButton("Sell 100%", callback_data='sell_100'),
            types.InlineKeyboardButton("X Sell", callback_data='sell')
        ]
        markup.row(trade_buttons[0], trade_buttons[1], trade_buttons[2], trade_buttons[3])  # 25 TON, 50 TON, 100 TON, X TON
        markup.row(trade_buttons[4], trade_buttons[5], trade_buttons[6], trade_buttons[7])
    elif action == 'limit':
        if buy_sell == 'sell':
            trade_buttons = [
                types.InlineKeyboardButton(f"✅ Sell 25%" if sell_pct == '25' else "❌ Sell 25%", callback_data='trade_sell_25'),
                types.InlineKeyboardButton(f"✅ Sell 50%" if sell_pct == '50' else "❌ Sell 50%", callback_data='trade_sell_50'),
                types.InlineKeyboardButton(f"✅ Sell 100%" if sell_pct == '100' else "❌ Sell 100%", callback_data='trade_sell_100'),
                types.InlineKeyboardButton(f"✅ Sell {sell_pct}%" if sell_pct != '25' and sell_pct != '50' and sell_pct != '100' else "❌ X Sell", callback_data='enter_sell_amt')
            ]
            amt_button_label = f"Enter {symbol} {sell_pct} %"
            amt_callback_data = 'enter_sell_amt'
        else:
            trade_buttons = [
                types.InlineKeyboardButton(f"✅ 25 TON" if ton_amt == '25' else "❌ 25 TON", callback_data='trade_buy_25'),
                types.InlineKeyboardButton(f"✅ 50 TON" if ton_amt == '50' else "❌ 50 TON", callback_data='trade_buy_50'),
                types.InlineKeyboardButton(f"✅ 100 TON" if ton_amt == '100' else "❌ 100 TON", callback_data='trade_buy_100'),
                types.InlineKeyboardButton(f"✅ {ton_amt} TON" if ton_amt != '25' and ton_amt != '50' and ton_amt != '100' else "❌ X TON", callback_data='enter_buy_amt')

            ]
            amt_button_label = f"Enter {ton_amt} TON"
            amt_callback_data = 'enter_buy_amt'

        markup.row(trade_buttons[0], trade_buttons[1], trade_buttons[2], trade_buttons[3])  # Trade buttons
        if ton_amt == 'X' or sell_pct == 'X':
            markup.row(types.InlineKeyboardButton(amt_button_label, callback_data=amt_callback_data))

    # Action Buttons
    action_buttons = [
        types.InlineKeyboardButton("✅ Swap" if action == 'swap' else "❌ Swap", callback_data='select_swap'),
        types.InlineKeyboardButton("✅ Limit" if action == 'limit' else "❌ Limit", callback_data='select_limit')
    ]
    markup.row(action_buttons[0], action_buttons[1])  # Swap, Limit

    # Buy/Sell Buttons for Limit Orders
    if action == 'limit':
        buy_sell_buttons = [
            types.InlineKeyboardButton("✅ Buy" if buy_sell == 'buy' else "❌ Buy", callback_data='select_buy'),
            types.InlineKeyboardButton("✅ Sell" if buy_sell == 'sell' else "❌ Sell", callback_data='select_sell')
        ]
        indicator_buttons = [
            types.InlineKeyboardButton("✅ Price" if indicator == 'price' else "❌ Price", callback_data='select_price'),
            types.InlineKeyboardButton("✅ % Change" if indicator == 'change' else "❌ % Change", callback_data='select_change'),
            types.InlineKeyboardButton("✅ MCap" if indicator == 'mcap' else "❌ MCap", callback_data='select_mcap')
        ]
        exp_button = types.InlineKeyboardButton(f"Exp {exp}", callback_data='enter_exp')

        markup.row(buy_sell_buttons[0], buy_sell_buttons[1])  # Buy, Sell
        markup.row(indicator_buttons[0], indicator_buttons[1], indicator_buttons[2])  # Price, % Change, MCap
        markup.row(exp_button)  # Expiration button
        markup.row(types.InlineKeyboardButton(f"Enter {indicator}: {format_number(format_price(indicator_value))}", callback_data='enter_indicator'))
        markup.row(types.InlineKeyboardButton("CREATE ORDER", callback_data='create_order'))

    # Platform Buttons
    platform_buttons = [
        types.InlineKeyboardButton("✅ DeDust" if user_sessions[user_id]['preferred_platform'] == 'DeDust' else "❌ DeDust", callback_data='select_dedust'),
        types.InlineKeyboardButton("✅ StonFi" if user_sessions[user_id]['preferred_platform'] == 'StonFi' else "❌ StonFi", callback_data='select_stonfi')
    ]
    markup.row(platform_buttons[0], platform_buttons[1])  # Platform buttons

    # Other Buttons
    markup.row(types.InlineKeyboardButton(f"Transfer {symbol}", callback_data='transfer_jetton'))
    markup.row(types.InlineKeyboardButton("Home", callback_data='cancel_transaction'))

    return markup

def handle_exp_selection(call):
    user_id = call.message.chat.id
    send_message_and_record(user_id, "Please enter the new expiration date and time in the format '1d 23h 15m':")
    bot.register_next_step_handler_by_chat_id(user_id, process_exp_date)

def process_exp_date(message):
    user_id = message.chat.id
    exp_pattern = r'^(\d+d)?\s*(\d+h)?\s*(\d+m)?$'
    exp_text = message.text.strip()

    match = re.fullmatch(exp_pattern, exp_text)
    if not match or not any(match.groups()):
        send_message_and_record(user_id, "Invalid format. Please enter the expiration date and time in the format '1d 23h 15m':")
        bot.register_next_step_handler(message, process_exp_date)
        return

    if user_id in last_messages and last_messages[user_id]:
        last_message_id = last_messages[user_id].pop()
        delete_message(user_id, last_message_id)
        delete_message(user_id, last_message_id + 1)

    # Remove None parts and strip spaces
    new_exp_parts = [part for part in match.groups() if part]
    new_exp = ' '.join(new_exp_parts)
    user_sessions[user_id]['exp'] = new_exp  # Ensure it's replaced, not appended

    # Refresh the markup with updated expiration date
    markup = generate_markup(user_id)
    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=user_sessions[user_id]['last_message_id'], reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit message: {e}")

def handle_enter_buy_amt(message):
    user_id = message.chat.id
    ton_amt = message.text.strip()

    # Validate input (should be a number)
    if not ton_amt.isdigit() or int(ton_amt) <= 0:
        send_message_and_record(user_id, "Invalid amount. Please enter a valid TON amount to buy:")
        bot.register_next_step_handler(message, handle_enter_buy_amt)
        return

    user_sessions[user_id]['ton_amt'] = ton_amt

    if user_id in last_messages and last_messages[user_id]:
        last_message_id = last_messages[user_id].pop()
        delete_message(user_id, last_message_id)
        delete_message(user_id, last_message_id + 1)

    # Refresh the markup with updated ton amount
    markup = generate_markup(user_id)
    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=user_sessions[user_id]['last_message_id'], reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit message: {e}")

def handle_enter_sell_amt(message):
    user_id = message.chat.id
    sell_pct = message.text.strip()

    # Validate input (should be a percentage between 1 and 100)
    if not sell_pct.isdigit() or not (1 <= int(sell_pct) <= 100):
        send_message_and_record(user_id, "Invalid percentage. Please enter a valid percentage (1-100) to sell:")
        bot.register_next_step_handler(message, handle_enter_sell_amt)
        return

    user_sessions[user_id]['sell_pct'] = sell_pct

    if user_id in last_messages and last_messages[user_id]:
        last_message_id = last_messages[user_id].pop()
        delete_message(user_id, last_message_id)
        delete_message(user_id, last_message_id + 1)

    # Refresh the markup with updated sell percentage
    markup = generate_markup(user_id)
    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=user_sessions[user_id]['last_message_id'], reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit message: {e}")

def handle_create_order(user_id):
    try:
        user_data = user_sessions[user_id]
        preferred_platform = user_data.get('preferred_platform', 'N/A')
        action = user_data.get('action', 'N/A')
        buy_sell = user_data.get('buy_sell', 'N/A')
        indicator = user_data.get('indicator', 'N/A')
        indicator_value = float(user_data.get(indicator, '0'))
        expiration = user_data.get('exp', 'N/A')
        ton_amount = float(user_data.get('ton_amt', '0'))
        token_name = user_data.get('name', 'N/A')
        token_symbol = user_data.get('symbol', 'N/A')
        current_price = float(user_data.get('price', '0'))
        total_supply = float(user_data.get('total_supply', '0'))
        ton_price_usd = float(user_data.get('ton_price_usd', '0'))
        sell_pct = user_data.get('sell_pct', '100')
        contract_address = user_data.get('jetton_contract_address', 'N/A')
        decimals = int(user_data.get('decimals', 9))
        status = 'pending'  # Initial status

        if buy_sell == 'sell':
            ton_amount = sell_pct

        if user_id in user_sessions and 'last_message_id' in user_sessions[user_id]:
            message_id = user_sessions[user_id]['last_message_id']
            try:
                delete_message(user_id, message_id)
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code == 400 and 'message to delete not found' in e.description:
                    pass  # Ignore this specific error
                else:
                    print(f"Failed to delete message {message_id}: {e}")

        wallet_address = get_wallet_address(user_id)

        # Fetch the user's jetton balance
        balance_init = get_jetton_balance(wallet_address, contract_address)
        balance = float(balance_init) / 10**decimals

        user_balance_tons = 0

        if wallet_address:
            user_balance, _ = asyncio.run(fetch_ton_balance(wallet_address))  # Assume balance is fetched in nanograms
            user_balance_tons = user_balance / 10**9
        else:
            user_balance = 0  # Default to 0 if no wallet found

        user_balance_tons = math.floor(user_balance_tons * 1000) / 1000

        if buy_sell == 'sell':
            if balance == 0:
                send_message_and_record(user_id, f"⚠️ You don't hold any *{token_symbol}* to set a sell limit.", parse_mode='Markdown')
                return
            ton_amount = sell_pct
        elif buy_sell == 'buy':
            if user_balance_tons < ton_amount:
                send_message_and_record(user_id, f"⚠️ Insufficient balance. Your balance is *{user_balance_tons:.3f}* TONs 💎, but you tried to set a limit with *{token_symbol}* for *{ton_amount}* TONs 💎.", parse_mode='Markdown')
                return

        # Calculate market cap
        market_cap = total_supply * current_price * ton_price_usd

        current_price_used = current_price * ton_price_usd

        # Calculate target price for % change
        if indicator == 'change':
            target_price = current_price * (1 + indicator_value / 100)
            change_direction = "increase" if indicator_value > 0 else "decrease"
            target_price_used = target_price * ton_price_usd

        # Insert the order into the database
        cursor = get_cursor()
        cursor.execute('''
        INSERT INTO orders (user_id, preferred_platform, action, buy_sell, indicator, indicator_value, expiration, ton_amount, token_name, token_symbol, contract_address, status, current_price, market_cap)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (user_id, preferred_platform, action, buy_sell, indicator, indicator_value, expiration, ton_amount, token_name, token_symbol, contract_address, status, current_price, market_cap))
        order_id = cursor.lastrowid
        db.commit()
        cursor.close()

        cap_direction = "increase" if indicator_value > market_cap else "decrease"

        # Generate the message based on the indicator type
        if indicator == 'mcap':
            message = (f"🧘‍♂️ *Chill!*\n"
                       f"The current Market Cap is `${format_number(format_price(market_cap))}`. automatically *{buy_sell}* for you when the market cap *{cap_direction}s* to `${format_number(format_price(indicator_value))}`.")
        elif indicator == 'change':
            message = (f"📉 *Market Change Alert!*\n"
                       f"The current price is `${format_number(format_price(current_price_used))}`. automatically *{buy_sell}* for you when the price *{change_direction}* by `{indicator_value:.2f}%` to `${format_number(format_price(target_price_used))}`.")
        elif indicator == 'price':
            target_price = indicator_value
            target_price_use = target_price * ton_price_usd
            price_direction = "increase" if target_price > current_price else "decrease"
            message = (f"📈 *Price Alert!*\n"
                       f"The current price is `${format_number(format_price(current_price_used))}`. automatically *{buy_sell}* for you when the price *{price_direction}s* to `${format_number(format_price(target_price_use))}`.")
        else:
            # Send the summary of the order to the user
            message = ("❌ Session expired. Please start again.")

        send_new_message_and_delete_last(user_id, message, parse_mode='Markdown')

        # Clear the user session data after order creation
        user_sessions[user_id].clear()

        order = fetch_order(order_id)

        # Start a new thread to monitor the order limits
        monitor_thread = threading.Thread(target=monitor_limits, args=(order_id, order,))
        monitor_thread.start()
    except Exception as e:
        logging.error(f"Failed to create order for user {user_id}: {e}")
        send_message_and_record(user_id, "❌ Failed to create order. Please try again later.")

def parse_expiration(expiration):
    days = hours = minutes = 0
    if 'd' in expiration:
        days = int(expiration.split('d')[0].strip())
        expiration = expiration.split('d')[1].strip()
    if 'h' in expiration:
        hours = int(expiration.split('h')[0].strip())
        expiration = expiration.split('h')[1].strip()
    if 'm' in expiration:
        minutes = int(expiration.split('m')[0].strip())
    return days * 86400 + hours * 3600 + minutes * 60

def monitor_limits(order_id, order):
    try:
        while True:
            try:
                user_id = float(order[1])
                indicator = order[5]  # Adjust according to your database schema
                indicator_value = float(order[6])  # Adjust according to your database schema
                contract_address = order[11]  # Adjust according to your database schema
                created_at = order[13]  # Adjust according to your database schema
                expiration = order[7]  # Adjust according to your database schema
            except (ValueError, IndexError) as e:
                logging.error(f"Failed to convert order data: {e}")
                return

            expiration_seconds = parse_expiration(expiration)
            order_age = (datetime.now() - created_at).total_seconds()

            if order_age > expiration_seconds:
                update_order_status(order_id, 'expired')
                send_message_and_record(user_id, f"⏰ Your order has expired. The expiration time of {expiration} has been reached.")
                return

            # Fetch metadata
            metadata = fetch_metadata(contract_address)
            if not validate_metadata(metadata):
                logging.error(f"Invalid metadata for contract address {contract_address}.")
                return

            jetton_info = extract_jetton_info(metadata)
            if jetton_info['name'] == 'N/A' and jetton_info['symbol'] == 'N/A':
                logging.error(f"Invalid jetton info for contract address {contract_address}.")
                return

            total_supply = float(jetton_info['total_supply'])

            ton_price_usd = fetch_ton_price_usd()

            current_price = fetch_current_price_in_ton(contract_address)

            market_cap = total_supply * current_price * ton_price_usd

            current_price_usd = current_price * ton_price_usd

            if indicator == 'mcap' and market_cap >= indicator_value:
                execute_order(order)
                break
            elif indicator == 'change':
                target_price = current_price * (1 + indicator_value / 100)
                if (indicator_value > 0 and current_price >= target_price) or (indicator_value < 0 and current_price <= target_price):
                    execute_order(order)
                    break
            elif indicator == 'price' and current_price_usd == indicator_value:
                execute_order(order)
                break

            time.sleep(5)  # Check every 5 seconds
    except Exception as e:
        logging.error(f"Failed to monitor order {order_id}: {e}")

def execute_order(order):
    try:
        user_id = int(order[1])  # Adjust according to your database schema
        preferred_platform = order[2]  # Adjust according to your database schema
        buy_sell = order[4]  # Adjust according to your database schema
        indicator = order[5]  # Adjust according to your database schema
        indicator_value = order[6]  # Adjust according to your database schema
        expiration = order[7]  # Adjust according to your database schema
        ton_amount = float(order[8])  # For buy, this is the amount; for sell, this is the percentage
        token_name = order[9]  # Adjust according to your database schema
        token_symbol = order[10]  # Adjust according to your database schema
        contract_address = order[11]  # Adjust according to your database schema

        metadata = fetch_metadata(contract_address)
        if not validate_metadata(metadata):
            return

        jetton_info = extract_jetton_info(metadata)
        if jetton_info['name'] == 'N/A' and jetton_info['symbol'] == 'N/A':
            return

        jetton_content = metadata.get('result', {}).get('jetton_content', {}).get('data', {})
        decimals = int(jetton_content.get('decimals', 9))

        user_wallet = get_wallet_address(user_id)
        balance_init = get_jetton_balance(user_wallet, contract_address)
        user_balance = float(balance_init) / 10**decimals

        total_supply = float(jetton_info['total_supply'])

        ton_price_usd = float(fetch_ton_price_usd())  # Convert to float

        current_price = float(fetch_current_price_in_ton(contract_address))  # Convert to float

        market_cap = total_supply * current_price * ton_price_usd

        current_price_usd = current_price * ton_price_usd

        # Placeholder for user mnemonics; replace with actual retrieval logic
        mnemonics = get_user_mnemonic(user_id)

        if buy_sell == 'buy':
            # Fetch jetton amount based on the ton amount and current price
            jetton_amount = ton_amount / current_price
            if preferred_platform == 'DeDust':
                asyncio.run(execute_buy_transaction(user_id, contract_address, ton_amount, jetton_amount, mnemonics, token_name, token_symbol))
            elif preferred_platform == 'StonFi':
                asyncio.run(execute_buy_transaction_stonfi(user_id, contract_address, ton_amount, jetton_amount, mnemonics, token_name, token_symbol))
        elif buy_sell == 'sell':
            # Fetch sell amount based on the ton amount and current price
            sell_amount = (ton_amount / 100) * user_balance
            ton_amount_used = sell_amount * current_price
            # Fetch decimals for accurate calculation; replace with actual logic
            if preferred_platform == 'DeDust':
                asyncio.run(execute_sell_transaction(user_id, contract_address, ton_amount_used, sell_amount, mnemonics, decimals, token_name, token_symbol))
            elif preferred_platform == 'StonFi':
                asyncio.run(execute_sell_transaction_stonfi(user_id, contract_address, ton_amount_used, sell_amount, mnemonics, decimals, token_name, token_symbol))

        # Update the order status in the database
        cursor = get_cursor()
        cursor.execute('UPDATE orders SET status = %s WHERE id = %s', ('success', order[0]))  # Corrected from 'order['id']' to 'order[0]'
        db.commit()
        cursor.close()

        # Send the summary of the order execution to the user
        if indicator == 'mcap':
            message = (f"🎉 *Success!*\n"
                       f"*{buy_sell}* order of *{token_symbol}* successfully executed at `${format_number(format_price(indicator_value))}`.")
        elif indicator == 'change':
            change_direction = "increased" if indicator_value > 0 else "decreased"
            target_price = current_price * (1 + float(indicator_value) / 100)  # Convert indicator_value to float
            target_price_used = target_price * ton_price_usd
            value_used = float(indicator_value)
            message = (f"🎉 *Success!*\n"
                       f"*{buy_sell}* order of *{token_symbol}* successfully executed at `{format_number(format_price(value_used))}%`.")
        elif indicator == 'price':
            price_direction = "increased" if float(indicator_value) > current_price else "decreased"  # Convert indicator_value to float
            target_price = float(indicator_value)  # Convert indicator_value to float
            message = (f"🎉 *Success!*\n"
                       f"*{buy_sell}* order of *{token_symbol}* successfully executed at targeted price `${format_number(format_price(target_price))}`.")
        else:
            message = (f"📋 *Order Summary:*\n"
                       f"🔹 *Platform:* {preferred_platform}\n"
                       f"🔹 *Buy/Sell:* {buy_sell}\n"
                       f"🔹 *Indicator:* {indicator} - {indicator_value}\n"
                       f"🔹 *Expiration:* {expiration}\n"
                       f"🔹 *TON Amount:* {ton_amount}\n"
                       f"🔹 *Token Name:* {token_name}\n"
                       f"🔹 *Token Symbol:* {token_symbol}\n"
                       f"🔹 *Contract Address:* {contract_address}\n"
                       f"🔹 *Current Price:* {current_price}\n"
                       f"🔹 *Market Cap:* {market_cap:.2f}\n"
                       f"🔹 *Status:* success\n")

        send_message_and_record(user_id, message, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Failed to execute order for user {user_id}: {e}")
        send_message_and_record(user_id, "❌ Failed to execute order. Please try again later.")

@bot.callback_query_handler(func=lambda call: call.data == 'limit_order')
def handle_limit_order(call):
    user_id = call.message.chat.id
    try:
        # Ensure user_sessions for user_id is initialized
        if user_id not in user_sessions:
            user_sessions[user_id] = {}

        ton_price_usd = fetch_ton_price_usd()

        orders = fetch_user_orders(user_id)
        if not orders:
            send_message_and_record(user_id, "📊 *You do not have any orders yet* 📊", parse_mode='Markdown')
            return

        position_messages = []

        for order in orders:
            order_id, status, action, indicator, indicator_value, expiration, ton_amount, token_name, token_symbol, current_price, market_cap, buy_sell = order
            if status == 'cancelled':
                continue

            current_price_used = ton_price_usd * float(current_price)

            amount_text = f"{format_number(format_price(ton_amount))} TON" if buy_sell == 'buy' else f"{format_number(format_price(ton_amount))}%"
            message_text = (f"📋 *Order ID:* `{order_id}`\n"
                            f"⏳ *Status:* `{status}`\n"
                            f"📊 *At:* *{indicator}* - `{format_number(format_price(indicator_value))}`\n"
                            f"⏱️ *Exp:* `{expiration}`\n"
                            f"💰 *Amount:* *{buy_sell}* `{amount_text}`\n"
                            f"🪙 *Token:* *{token_name}* (*{token_symbol}*)\n"
                            f"📈 *Initial Price:* `${format_number(format_price(current_price_used))}`\n"
                            f"\n")

            markup = types.InlineKeyboardMarkup()
            if status == 'pending':
                cancel_button = types.InlineKeyboardButton(f"Cancel Order {order_id}", callback_data=f'cancel_order_{order_id}')
                back_button = types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main')
                markup.add(cancel_button, back_button)

            sent_message = bot.send_message(user_id, message_text, reply_markup=markup, parse_mode='Markdown')
            if sent_message:
                position_messages.append(sent_message.message_id)

        user_sessions[user_id]['position_messages'] = position_messages
    except Exception as e:
        logging.error(f"Failed to handle limit order for user {user_id}: {str(e)}")
        send_message_and_record(user_id, "❌ Failed to retrieve orders. Please try again later.", parse_mode='Markdown')

def handle_enter_indicator(message):
    user_id = message.chat.id
    indicator = user_sessions[user_id].get('indicator', 'mcap')
    indicator_value = message.text.strip()

    if indicator == 'price':
        # Validate that the input is a valid price (positive number)
        try:
            price = float(indicator_value)
            if price <= 0:
                raise ValueError
            user_sessions[user_id]['price'] = price
        except ValueError:
            send_message_and_record(user_id, "Invalid price. Please enter a valid price:")
            bot.register_next_step_handler(message, handle_enter_indicator)
            return

    elif indicator == 'change':
        # Validate that the input is a valid percentage change (integer)
        try:
            change = int(indicator_value)
            user_sessions[user_id]['change'] = change
        except ValueError:
            send_message_and_record(user_id, "Invalid percentage change. Please enter a valid percentage change:")
            bot.register_next_step_handler(message, handle_enter_indicator)
            return

    elif indicator == 'mcap':
        # Validate that the input is a valid market cap format (e.g., 157.43k or 5.34m)
        mcap_pattern = r'^(\d+(\.\d+)?)([km])?$'
        match = re.fullmatch(mcap_pattern, indicator_value.lower())
        if not match:
            send_message_and_record(user_id, "Invalid market cap. Please enter a valid market cap (e.g., 157.43k or 5.34m):")
            bot.register_next_step_handler(message, handle_enter_indicator)
            return

        # Convert the market cap to full digits
        value, _, suffix = match.groups()
        value = float(value)
        if suffix == 'k':
            value *= 1_000
        elif suffix == 'm':
            value *= 1_000_000
        user_sessions[user_id]['mcap'] = value

    if user_id in last_messages and last_messages[user_id]:
        last_message_id = last_messages[user_id].pop()
        delete_message(user_id, last_message_id)
        delete_message(user_id, last_message_id + 1)

    # Refresh the markup with updated indicator value
    markup = generate_markup(user_id)
    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=user_sessions[user_id]['last_message_id'], reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit message: {e}")

def handle_platform_selection(call):
    user_id = call.message.chat.id
    selected_platform = 'DeDust' if call.data == 'select_dedust' else 'StonFi'
    user_sessions[user_id]['preferred_platform'] = selected_platform

    # Refresh the markup with updated button states
    markup = generate_markup(user_id)

    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=user_sessions[user_id]['last_message_id'], reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit message: {e}")

def handle_action_selection(call):
    user_id = call.message.chat.id
    selected_action = 'swap' if call.data == 'select_swap' else 'limit'
    user_sessions[user_id]['action'] = selected_action

    # Refresh the markup with updated button states
    markup = generate_markup(user_id)

    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=user_sessions[user_id]['last_message_id'], reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit message: {e}")

def handle_buy_sell_selection(call):
    user_id = call.message.chat.id
    selected_buy_sell = 'buy' if call.data == 'select_buy' else 'sell'
    user_sessions[user_id]['buy_sell'] = selected_buy_sell

    # Refresh the markup with updated button states
    markup = generate_markup(user_id)

    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=user_sessions[user_id]['last_message_id'], reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit message: {e}")

def handle_indicator_selection(call):
    user_id = call.message.chat.id
    selected_indicator = 'price' if call.data == 'select_price' else 'change' if call.data == 'select_change' else 'mcap'
    user_sessions[user_id]['indicator'] = selected_indicator

    # Refresh the markup with updated button states
    markup = generate_markup(user_id)

    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=user_sessions[user_id]['last_message_id'], reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit message: {e}")

def validate_metadata(metadata):
    try:
        required_keys = ['mintable', 'total_supply', 'admin', 'metadata']
        return all(key in metadata for key in required_keys)
    except Exception as e:
        return

def extract_jetton_info(metadata):
    metadata_content = metadata.get('metadata', {})
    return {
        'name': metadata_content.get('name', 'N/A'),
        'symbol': metadata_content.get('symbol', 'N/A'),
        'image_url': metadata_content.get('image', 'N/A'),
        'description': metadata_content.get('description', 'N/A'),
        'decimals': int(metadata_content.get('decimals', 9)),
        'mintable': metadata.get('mintable', False),
        'total_supply': int(metadata.get('total_supply', 0)) / 10**int(metadata_content.get('decimals', 9))
    }


def prepare_metadata_message(user_id, jetton_info, balance, user_balance_tons, decimals, jetton_contract_address, preferred_dex):
    return (
        f"Buy <b>{jetton_info['symbol']} - ({jetton_info['name']})</b> - 🏦 {preferred_dex}\n"
        f"<code>{jetton_contract_address}</code>\n\n"
        f"💎 <b>Balance:</b> {format_number(user_balance_tons)} <b>TONs</b>\n"
        f"💰 <b>{jetton_info['symbol']} Balance:</b> {format_number(balance)} <b>{jetton_info['symbol']}</b>\n"
    )

def prepare_pool_message_from_api(pool_data, ton_price_usd, symbol, total_supply, decimals):
    attributes = pool_data['data']['attributes']

    # Check if 'base_token_price_quote_token' exists in the attributes
    price = float(attributes.get('base_token_price_quote_token', 0))

    # Check if 'reserve_in_usd' exists in the attributes
    reserve_native_usd = float(attributes.get('reserve_in_usd', 0))
    reserve_native_usd_1 = reserve_native_usd / 2
    reserve_native = reserve_native_usd_1 / ton_price_usd

    # As 'token_reserves' does not exist, we'll use 'reserve_in_usd' and divide by TON price in USD
    reserve_jetton = float(attributes.get('volume_usd', {}).get('h24', 0)) / ton_price_usd

    market_cap = total_supply * price * ton_price_usd

    market_cap_ton = total_supply * price

    # Extract additional information if available
    price_usd = attributes.get('base_token_price_usd', 'N/A')
    price_change_5m = attributes.get('price_change_percentage', {}).get('m5', 'N/A')
    price_change_1h = attributes.get('price_change_percentage', {}).get('h1', 'N/A')
    price_change_24h = attributes.get('price_change_percentage', {}).get('h24', 'N/A')
    buys = attributes.get('transactions', {}).get('h24', {}).get('buys', 'N/A')
    sells = attributes.get('transactions', {}).get('h24', {}).get('sells', 'N/A')
    volume_24h = attributes.get('volume_usd', {}).get('h24', 'N/A')
    age = attributes.get('pool_created_at', 'N/A')

    # Calculate age in detailed format
    if age != 'N/A':
        age_datetime = datetime.strptime(age, '%Y-%m-%dT%H:%M:%SZ')
        age_timedelta = datetime.now() - age_datetime
        age_days = age_timedelta.days
        age_hours, remainder = divmod(age_timedelta.seconds, 3600)
        age_minutes, _ = divmod(remainder, 60)
        age_detailed = f"{age_days} days, {age_hours} hours, {age_minutes} minutes"
    else:
        age_detailed = 'N/A'

    # Extract holders information if available
    holders = "N/A"
    if 'relationships' in pool_data['data']:
        holders_data = pool_data['data']['relationships'].get('dex', {}).get('data', {})
        if holders_data:
            holders = f"{holders_data.get('id', 'N/A')}: {holders_data.get('type', 'N/A')}"

    pool_message = (
        f"💎 <b>MCap:</b> ${format_number(format_price(market_cap))} | {format_number(format_price(market_cap_ton))} TON\n"
        f"💲 <b>Price:</b> ${format_number(format_price(price_usd))} 5m {price_change_5m}% 1h {price_change_1h}% 24h {price_change_24h}%\n"
        f"📊  <b>Buys:</b> {buys}  <b>Sells:</b> {sells}  <b>Volume 24h:</b> {format_number(format_price(volume_24h))}\n"
        f"💧 <b>TON in LP:</b> {format_number(reserve_native)} TON\n"
        f"🕰️ <b>Age:</b> {age_detailed}\n"
        f"🍰 <b>Supply:</b> {format_number(format_price(total_supply))}\n"
        f"✅ <b>Ownership renounced:</b> Yes\n"
    )
    return {'message': pool_message, 'price': price}

@bot.callback_query_handler(func=lambda call: call.data == 'transfer_jetton')
def handle_transfer_jetton(call):
    user_id = call.message.chat.id
    session = user_sessions.get(user_id)

    if not session:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        handle_skip_now(user_id)
        return

    symbol = session['symbol']
    msg = send_new_message_and_delete_last(user_id, f"Enter the amount of *{symbol}* you want to transfer:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, ask_transfer_jetton_amount)

def ask_transfer_jetton_amount(message):
    user_id = message.chat.id
    amount = float(message.text)

    session = user_sessions.get(user_id)
    try:
        if not session:
            send_message_and_record(user_id, "❌ Session expired. Please start again.")
            handle_skip_now(user_id)
            return

        user_balance = session['user_balance']
        if amount > user_balance:
            send_message_and_record(user_id, f"❌ Insufficient balance. You have *{format_price(user_balance)} {session['symbol']}*.", parse_mode='Markdown')
            handle_jettons_contract(user_id, session['jetton_contract_address'])
            return

        session['transfer_amount'] = amount

        msg = send_new_message_and_delete_last(user_id, "Enter the recipient's address:")
        bot.register_next_step_handler(msg, ask_transfer_jetton_recipient)
    except ValueError:
        send_message_and_record(message.chat.id, "❌ Invalid amount entered. Please Retry")
        handle_jettons_contract(user_id, session['jetton_contract_address'])

def ask_transfer_jetton_recipient(message):
    user_id = message.chat.id
    recipient_address = message.text.strip()

    session = user_sessions.get(user_id)
    if not session:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        handle_skip_now(user_id)
        return

    session['recipient_address'] = recipient_address

    amount = session['transfer_amount']
    symbol = session['symbol']

    confirmation_message = (
        f"🔸 *Transfer Confirmation* 🔸\n\n"
        f"💰 Amount to transfer: *{format_price(amount)} {symbol}*\n"
        f"📬 Recipient address: `{recipient_address}`\n\n"
        f"Do you want to proceed with the transfer?"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data='confirm_transfer_jetton')
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
    markup.add(confirm_button, cancel_button)

    send_new_message_and_delete_last(user_id, confirmation_message, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_transfer_jetton')
def confirm_transfer_jetton(call):
    user_id = call.message.chat.id

    session = user_sessions.get(user_id)
    if not session:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        handle_skip_now(user_id)
        return

    jetton_contract_address = session['jetton_contract_address']
    transfer_amount = session['transfer_amount']
    recipient_address = session['recipient_address']
    mnemonics = get_user_mnemonic(user_id)  # Replace with your method to get user's mnemonics

    asyncio.run(execute_transfer_jetton(user_id, jetton_contract_address, transfer_amount, recipient_address, mnemonics, session['decimals']))

async def execute_transfer_jetton(user_id, jetton_contract_address, transfer_amount, recipient_address, mnemonics, decimals):
    try:
        session = user_sessions.get(user_id)
        send_new_message_and_delete_last(user_id, f"💸 _Transferring {transfer_amount} {session['symbol']}..._", parse_mode='Markdown')
        # Initialize the LiteBalancer with mainnet configuration
        provider = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await provider.start_up()

        # Create a wallet instance using the provided mnemonics
        wallet = await WalletV4R2.from_mnemonic(provider=provider, mnemonics=mnemonics.split())

        USER_ADDRESS = wallet.address
        JETTON_MASTER_ADDRESS = Address(jetton_contract_address)
        DESTINATION_ADDRESS = Address(recipient_address)

        # Obtain the user's jetton wallet address
        USER_JETTON_WALLET = (await provider.run_get_method_local(
            address=JETTON_MASTER_ADDRESS,
            method="get_wallet_address",
            stack=[begin_cell().store_address(USER_ADDRESS).end_cell().begin_parse()]
        ))[0].load_address()

        # Create the forward payload
        forward_payload = (begin_cell()
                          .store_uint(0, 32)  # TextComment op-code
                          .store_snake_string("Comment")
                          .end_cell())

        # Create the transfer cell
        transfer_cell = (begin_cell()
                        .store_uint(0xf8a7ea5, 32)          # Jetton Transfer op-code
                        .store_uint(0, 64)                  # query_id
                        .store_coins(int(transfer_amount * 10**decimals))  # Jetton amount to transfer in nanojetton
                        .store_address(DESTINATION_ADDRESS) # Destination address
                        .store_address(USER_ADDRESS)        # Response address
                        .store_bit(0)                       # Custom payload is None
                        .store_coins(1)                     # Ton forward amount in nanoton
                        .store_bit(1)                       # Store forward_payload as a reference
                        .store_ref(forward_payload)         # Forward payload
                        .end_cell())

        # Execute the transfer
        await wallet.transfer(destination=USER_JETTON_WALLET, amount=int(0.05 * 1e9), body=transfer_cell)

        # Close the provider
        await provider.close_all()

        markup = types.InlineKeyboardMarkup()
        cancel_button = types.InlineKeyboardButton("✅ Done", callback_data='cancel_transaction')
        markup.add(cancel_button)

        send_message_and_record(user_id, f"✅ Successfully  Submitted! Transfer of *{format_price(transfer_amount)} {session['symbol']}* to `{recipient_address}`.", parse_mode='Markdown')

        del user_sessions[user_id]  # Delete user session

        await handle_skip_now_now(user_id)

    except Exception as e:
        send_message_and_record(user_id, f"❌ An error occurred during the transfer: ```{e}```", parse_mode='Markdown')
        if user_id in user_sessions:
            del user_sessions[user_id]
        await handle_skip_now_now(user_id)

@bot.callback_query_handler(func=lambda call: call.data == 'buy')
def handle_buy(call):
    user_id = call.message.chat.id
    session = user_sessions.get(user_id)

    symbol = session['symbol']

    # Send a message asking for the amount to spend in TON
    msg = send_new_message_and_delete_last(user_id, f"Enter the amount of *TONs* 💎 you want to Buy the *{symbol}* With:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, ask_buy_amount)

def ask_buy_amount(message):
    user_id = message.chat.id

    # Fetch session data
    session = user_sessions.get(user_id)
    try:
        ton_amount = float(message.text)

        if not session:
            send_message_and_record(user_id, "❌ Session expired. Please start again.")
            handle_skip_now(user_id)
            return

        jetton_price = session.get('price')
        if jetton_price is None:
            send_message_and_record(user_id, "❌ Unable to determine the jetton price.")
            handle_jettons_contract(user_id, session['jetton_contract_address'])
            return

        # Calculate the number of jettons to buy
        jetton_amount = ton_amount / jetton_price

        # Store transaction details in the session
        session['ton_amount'] = ton_amount
        session['jetton_amount'] = jetton_amount

        wallet_address = get_wallet_address(user_id)

        if wallet_address:
            user_balance, status = asyncio.run(fetch_ton_balance(wallet_address))  # Assume balance is fetched in nanograms
            user_balance_tons = user_balance / 10**9
        else:
            user_balance = 0  # Default to 0 if no wallet found

        user_balance_tons = math.floor(user_balance_tons * 1000) / 1000

        if user_balance_tons < ton_amount:
            send_message_and_record(user_id, f"⚠️ Insufficient balance. Your balance is *{user_balance_tons:.3f}* TONs 💎, but you tried to Buy *{session['symbol']}* for *{ton_amount}* TONs 💎.", parse_mode='Markdown')
            return

        # Ask for confirmation
        markup = types.InlineKeyboardMarkup(row_width=2)
        confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data='confirm_buy')
        cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
        markup.add(confirm_button, cancel_button)

        send_new_message_and_delete_last(
            user_id,
            f"You are about to buy *{format_price(jetton_amount)} {session['symbol']}* for *{format_price(ton_amount)}* TONs 💎.\nDo you want to proceed?",
            reply_markup=markup,
            parse_mode='Markdown'
        )

    except ValueError:
        send_message_and_record(message.chat.id, "❌ Invalid amount entered. Please Retry.")
        handle_jettons_contract(user_id, session['jetton_contract_address'])

def ask_buy_amount_direct(call):
    user_id = call.message.chat.id

    # Fetch session data
    session = user_sessions.get(user_id)
    if not session:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        handle_skip_now(user_id)
        return

    try:
        ton_amount = int(call.data.split('_')[1])

        jetton_price = session.get('price')
        if jetton_price is None:
            send_message_and_record(user_id, "❌ Unable to determine the jetton price.")
            handle_jettons_contract(user_id, session['jetton_contract_address'])
            return

        # Calculate the number of jettons to buy
        jetton_amount = ton_amount / jetton_price

        # Store transaction details in the session
        session['ton_amount'] = ton_amount
        session['jetton_amount'] = jetton_amount

        wallet_address = get_wallet_address(user_id)

        if wallet_address:
            user_balance, status = asyncio.run(fetch_ton_balance(wallet_address))  # Assume balance is fetched in nanograms
            user_balance_tons = user_balance / 10**9
        else:
            user_balance_tons = 0  # Default to 0 if no wallet found

        user_balance_tons = math.floor(user_balance_tons * 1000) / 1000

        if user_balance_tons < ton_amount:
            send_message_and_record(user_id, f"⚠️ Insufficient balance. Your balance is *{user_balance_tons:.3f}* TONs 💎, but you tried to Buy *{session['symbol']}* for *{ton_amount}* TONs 💎.", parse_mode='Markdown')
            return

        # Ask for confirmation
        markup = types.InlineKeyboardMarkup(row_width=2)
        confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data='confirm_buy')
        cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
        markup.add(confirm_button, cancel_button)

        send_new_message_and_delete_last(
            user_id,
            f"You are about to buy *{format_price(jetton_amount)} {session['symbol']}* for *{format_price(ton_amount)}* TONs 💎.\nDo you want to proceed?",
            reply_markup=markup,
            parse_mode='Markdown'
        )

    except ValueError:
        send_message_and_record(call.message.chat.id, "❌ Invalid amount entered. Please Retry.")
        handle_jettons_contract(user_id, session['jetton_contract_address'])
    except Exception as e:
        send_message_and_record(user_id, f"❌ An error occurred: {e}")
        handle_skip_now(user_id)

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_buy')
def confirm_buy(call):
    try:
        user_id = call.message.chat.id

        # Fetch session data
        session = user_sessions.get(user_id)
        if not session:
            send_message_and_record(user_id, "❌ Session expired. Please start again.")
            handle_skip_now(user_id)
            return

        jetton_contract_address = session['jetton_contract_address']
        ton_amount = session['ton_amount']
        jetton_amount = session['jetton_amount']
        mnemonics = get_user_mnemonic(user_id)  # Replace this with your method to get user's mnemonics

        name = session['name']
        symbol = session['symbol']

        preferred_platform = session.get('preferred_platform', 'StonFi')

        if preferred_platform == 'StonFi':
            asyncio.run(execute_buy_transaction_stonfi(user_id, jetton_contract_address, ton_amount, jetton_amount, mnemonics, name, symbol))
        elif preferred_platform == 'DeDust':
            asyncio.run(execute_buy_transaction(user_id, jetton_contract_address, ton_amount, jetton_amount, mnemonics, name, symbol))
        else:
            asyncio.run(execute_buy_transaction_stonfi(user_id, jetton_contract_address, ton_amount, jetton_amount, mnemonics, name, symbol))

    except Exception as e:
        send_message_and_record(call.message.chat.id, f"Error: {e}")

async def execute_buy_transaction(user_id, jetton_contract_address, ton_amount, jetton_amount, mnemonics, name, symbol):
    session = user_sessions.get(user_id)
    try:
        send_new_message_and_delete_last(user_id, f"💸 _Buying {symbol} for {ton_amount} TONs 💎..._", parse_mode='Markdown')

        # Initialize the LiteBalancer with mainnet configuration
        provider = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await provider.start_up()

        # Create wallet instance
        wallet = await WalletV4R2.from_mnemonic(provider=provider, mnemonics=mnemonics.split())

        TON = Asset.native()
        SCALE = Asset.jetton(jetton_contract_address)

        pool = await Factory.get_pool(pool_type=PoolType.VOLATILE,
                                      assets=[TON, SCALE],
                                      provider=provider)

        swap_params = SwapParams(deadline=int(time.time() + 60 * 5),
                                 recipient_address=wallet.address)
        swap_amount = int(ton_amount * 1e9)  # Convert TON amount to nanoTONs

        swap = VaultNative.create_swap_payload(amount=swap_amount,
                                               pool_address=pool.address,
                                               swap_params=swap_params)

        swap_amount_with_gas = int(swap_amount + (0.25 * 1e9))  # Add 0.25 TON for gas

        await wallet.transfer(destination="EQDa4VOnTYlLvDJ0gZjNYm5PXfSmmtL6Vs6A_CZEtXCNICq_",  # native vault
                              amount=swap_amount_with_gas,
                              body=swap)

        # Calculate the 0.8% fee in TON
        transfer_fee_amount = ton_amount * 0.008

        # Transfer the 0.8% fee in TON to the specified address
        fee_recipient_address = Address("UQAavflV2h5P5x7bFqB5mISfEDqRC0fp_s8zyxg4PjElH56t")

        # Update the referral balance with 10% of the 0.8%
        referral_bonus = transfer_fee_amount * 0.2

        await provider.close_all()

        # Send confirmation message with details
        send_message_and_record(user_id, f"✅ Successfully  Submitted\n\n"
                                  f"💸 Amount Spent: *{format_price(ton_amount)} TONs* 💎\n"
                                  f"💰 Amount to Receive: *{format_price(jetton_amount)} {symbol}*\n",
                                  parse_mode='Markdown')

        # Insert the new position into the database
        insert_or_update_user_position(user_id, name, symbol, jetton_contract_address, ton_amount, jetton_amount)
        await execute_transfer_fee(user_id, transfer_fee_amount, fee_recipient_address)
        await update_referral_balance(user_id, referral_bonus)

        # Delete user session
        del user_sessions[user_id]
    except Exception as e:
        send_message_and_record(user_id, f"❌ An error occurred please try again: ```{e}```", parse_mode='Markdown')
        await handle_skip_now_now(user_id)
        if user_id in user_sessions:
            del user_sessions[user_id]

async def execute_buy_transaction_stonfi(user_id, jetton_contract_address, ton_amount, jetton_amount, mnemonics, name, symbol):
    session = user_sessions.get(user_id)
    try:
        send_new_message_and_delete_last(user_id, f"💸 _Buying {symbol} for {ton_amount} TONs 💎..._", parse_mode='Markdown')

        # Initialize the LiteBalancer with mainnet configuration
        provider = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await provider.start_up()

        # Create wallet instance
        wallet: WalletV4R2 = await WalletV4R2.from_mnemonic(provider, mnemonics.split())

        # Build swap transaction parameters
        params = await router.build_swap_ton_to_jetton_tx_params(
            user_wallet_address=wallet.address,
            ask_jetton_address=Address(jetton_contract_address),
            offer_amount=int(ton_amount * 1e9),  # Convert TON amount to nanoTONs
            min_ask_amount=1,  # Convert Jetton amount to nanoJettons
            provider=provider,
            proxy_ton_address=PTON_V1_ADDRESS
        )

        # Execute the swap
        resp = await wallet.transfer(
            params['to'],
            params['amount'],
            params['payload']
        )

        await provider.close_all()

        # Check if the transaction was successful
        if resp != 1:
            raise Exception("Swap transaction failed.")

        # Calculate the 0.8% fee in TON
        transfer_fee_amount = ton_amount * 0.008

        # Transfer the 0.8% fee in TON to the specified address
        fee_recipient_address = Address("UQAavflV2h5P5x7bFqB5mISfEDqRC0fp_s8zyxg4PjElH56t")

        # Update the referral balance with 10% of the 0.8%
        referral_bonus = transfer_fee_amount * 0.2

        # Send confirmation message with details
        send_message_and_record(user_id, f"✅ Successfully  Submitted\n\n"
                                  f"💸 Amount Spent: *{format_price(ton_amount)} TONs* 💎\n"
                                  f"💰 Amount to Receive: *{format_price(jetton_amount)} {symbol}*\n",
                                  parse_mode='Markdown')

        # Insert the new position into the database
        insert_or_update_user_position(user_id, name, symbol, jetton_contract_address, ton_amount, jetton_amount)

        # Handle post-transaction steps
        await execute_transfer_fee(user_id, transfer_fee_amount, fee_recipient_address)
        await update_referral_balance(user_id, referral_bonus)

        # Delete user session
        del user_sessions[user_id]
    except Exception as e:
        send_message_and_record(user_id, f"❌ An error occurred please try again: ```{e}```", parse_mode='Markdown')
        await handle_skip_now_now(user_id)
        if user_id in user_sessions:
            del user_sessions[user_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('sell'))
def sell_jetton(call):
    user_id = call.message.chat.id

    # Fetch session data
    session = user_sessions.get(user_id)

    if not session:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        handle_skip_now(user_id)
        return

    # Ask the user how much jetton they want to sell
    msg = send_new_message_and_delete_last(user_id, f"Enter the amount of *{session['symbol']}* you want to sell, or choose a percentage below:", parse_mode='Markdown')

    send_new_message_and_delete_last(user_id, f"enter amount of *{session['symbol']}* you want to sell:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_sell_amount)

@bot.message_handler(func=lambda message: user_sessions.get(message.chat.id, {}).get('stage') == 'ask_sell_amount')
def process_sell_amount(message):
    user_id = message.chat.id
    session = user_sessions.get(user_id)
    try:
        # Convert the input to a float
        sell_amount = float(message.text)
    except ValueError:
        send_message_and_record(user_id, "❌ Invalid amount. Please Retry again.")
        handle_jettons_contract(user_id, session['jetton_contract_address'])
        return

    if not session:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        handle_skip_now(user_id)
        return

    # Check the user's balance
    user_balance = session['user_balance']
    if sell_amount > user_balance:
        send_message_and_record(user_id, f"❌ Insufficient balance. You have *{user_balance} {session['symbol']}*.", parse_mode='Markdown')
        handle_jettons_contract(user_id, session['jetton_contract_address'])
        return

    # Update session with the sell amount
    session['sell_amount'] = sell_amount

    # Calculate the equivalent TON amount
    try:
        ton_amount = session['price'] * sell_amount
    except Exception as e:
        send_message_and_record(user_id, f"❌ Error calculating TON amount: ```{e}```", parse_mode='Markdown')
        handle_jettons_contract(user_id, session['jetton_contract_address'])
        return

    # Update session with the TON amount
    session['ton_amount'] = ton_amount

    # Confirm the transaction
    confirmation_message = (
        f"🔸 *Sell Confirmation* 🔸\n\n"
        f"💰 Amount to sell: *{format_price(sell_amount)} {session['symbol']}*\n"
        f"💎 Amount to receive: *{format_price(ton_amount)} TONs 💎*\n\n"
        f"Do you want to proceed with the sell transaction?"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data='confirm_sell')
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
    markup.add(confirm_button, cancel_button)
    send_new_message_and_delete_last(user_id, confirmation_message, reply_markup=markup, parse_mode='Markdown')

def sell_percentage(call):
    user_id = call.message.chat.id
    session = user_sessions.get(user_id)
    if not session:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        handle_skip_now(user_id)
        return

    percentage = int(call.data.split('_')[1])
    sell_amount = session['user_balance'] * (percentage / 100)

    session['sell_amount'] = sell_amount

    user_balance = session['user_balance']
    if user_balance == 0:
        send_message_and_record(user_id, f"❌ 0 *{session['symbol']}* balance.", parse_mode='Markdown')
        handle_jettons_contract(user_id, session['jetton_contract_address'])
        return

    # Calculate the equivalent TON amount
    try:
        ton_amount = session['price'] * sell_amount
    except Exception as e:
        send_message_and_record(user_id, f"❌ Error calculating TON amount: ```{e}```", parse_mode='Markdown')
        handle_jettons_contract(user_id, session['jetton_contract_address'])
        return

    session['ton_amount'] = ton_amount

    # Confirm the transaction
    confirmation_message = (
        f"🔸 *Sell Confirmation* 🔸\n\n"
        f"💰 Amount to sell: *{format_price(sell_amount)} {session['symbol']}*\n"
        f"💎 Amount to receive: *{format_price(ton_amount)} TONs 💎*\n\n"
        f"Do you want to proceed with the sell transaction?"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data='confirm_sell')
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
    markup.add(confirm_button, cancel_button)
    send_new_message_and_delete_last(user_id, confirmation_message, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_sell')
def confirm_sell(call):
    try:
        user_id = call.message.chat.id

        # Fetch session data
        session = user_sessions.get(user_id)
        if not session:
            send_message_and_record(user_id, "❌ Session expired. Please start again.")
            handle_skip_now(user_id)
            return

        jetton_contract_address = session['jetton_contract_address']
        ton_amount = session['ton_amount']
        sell_amount = session['sell_amount']
        name = session['name']
        symbol = session['symbol']
        mnemonics = get_user_mnemonic(user_id)  # Replace this with your method to get user's mnemonics

        preferred_platform = session.get('preferred_platform', 'StonFi')

        if preferred_platform == 'StonFi':
            asyncio.run(execute_sell_transaction_stonfi(user_id, jetton_contract_address, ton_amount, sell_amount, mnemonics, session['decimals'], name, symbol))
        elif preferred_platform == 'DeDust':
            asyncio.run(execute_sell_transaction(user_id, jetton_contract_address, ton_amount, sell_amount, mnemonics, session['decimals'], name, symbol))
        else:
            asyncio.run(execute_sell_transaction_stonfi(user_id, jetton_contract_address, ton_amount, sell_amount, mnemonics, session['decimals'], name, symbol))

    except Exception as e:
        send_message_and_record(call.message.chat.id, f"Error: {e}")

def fetch_transaction_hash(wallet_address):
    try:
        url = f"https://tonapi.io/v2/accounts/{wallet_address}/events?limit=10"
        response = requests.get(url)
        response.raise_for_status()
        events = response.json().get('events', [])
        if events:
            return events[0].get('event_id', 'N/A')
        else:
            return 'N/A'
    except Exception as e:
        print(f"Error fetching transaction hash: {str(e)}")
        return 'N/A'

async def execute_sell_transaction(user_id, jetton_contract_address, ton_amount, sell_amount, mnemonics, decimals, name, symbol):

    session = user_sessions.get(user_id)
    try:
        send_new_message_and_delete_last(user_id, f"💸 _Selling {sell_amount} {symbol} for TONs 💎..._", parse_mode='Markdown')

        current_price = fetch_current_price_in_ton(jetton_contract_address)

        initial_data = fetch_initial_price_and_buy_time(user_id, jetton_contract_address)
        if not initial_data:
            raise Exception("Initial price and buy time data not found")

        initial_price = float(initial_data['initial_price'])
        buy_time = initial_data['buy_time']

        duration = datetime.now() - buy_time
        duration_st = format_duration(duration)
        duration_str = f"{duration_st}"
        profit = ((current_price - initial_price) / initial_price) * 100

        pair = f"{session['symbol']} / TON"
        value_str = f"{profit:.2f}%"

        # Transaction operations: initializing LiteBalancer, creating wallet, and executing the swap
        provider = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await provider.start_up()
        wallet = await WalletV4R2.from_mnemonic(provider=provider, mnemonics=mnemonics.split())
        SCALE = Asset.jetton(jetton_contract_address)
        TON = Asset.native()
        pool = await Factory.get_pool(PoolType.VOLATILE, [TON, SCALE], provider)
        scale_vault = await Factory.get_jetton_vault(jetton_contract_address, provider)
        scale_root = JettonRoot.create_from_address(jetton_contract_address)
        scale_wallet = await scale_root.get_wallet(wallet.address, provider)

        swap_amount = int(sell_amount * 10**decimals)
        swap = scale_wallet.create_transfer_payload(
            destination=scale_vault.address,
            amount=swap_amount,
            response_address=wallet.address,
            forward_amount=int(0.25 * 1e9),
            forward_payload=VaultJetton.create_swap_payload(pool_address=pool.address)
        )

        resp = await wallet.transfer(destination=scale_wallet.address, amount=int(0.3 * 1e9), body=swap)

        owner_address = get_wallet_address(user_id)

        try:
            resp = await wallet.transfer(destination=scale_wallet.address, amount=int(0.3 * 1e9), body=swap)
            if resp != 1:
                raise Exception("Swap transaction failed.")
        except Exception as e:
            if "exitcode=-14" in str(e):
                send_message_and_record(user_id, f"❌ *Transaction failed due to Insufficient Gas*", parse_mode='Markdown')
                if user_id in user_sessions:
                    del user_sessions[user_id]
                await handle_skip_now_now(user_id)
                return


        await provider.close_all()

        send_banner_image(user_id, pair, value_str, duration_str, profit, owner_address, ton_amount, sell_amount)

        # Calculate and handle fees
        transfer_fee_amount = ton_amount * 0.008
        fee_recipient_address = Address("UQAavflV2h5P5x7bFqB5mISfEDqRC0fp_s8zyxg4PjElH56t")
        referral_bonus = round(transfer_fee_amount * 0.2, 20)

        await execute_transfer_fee(user_id, transfer_fee_amount, fee_recipient_address)
        await update_referral_balance(user_id, referral_bonus)

        balance_init = get_jetton_balance(owner_address, jetton_contract_address)
        balance = float(balance_init) / 10**decimals

        # Corrected the parameters to be strings instead of sets
        update_user_position_if_needed(user_id, symbol, jetton_contract_address, balance, current_price)

        # Delete user session if necessary
        del user_sessions[user_id]

    except Exception as e:
        if "exitcode=-14" in str(e):
            send_message_and_record(user_id, f"❌ *Transaction failed due to Insufficient Gas*", parse_mode='Markdown')
            await handle_skip_now_now(user_id)
            if user_id in user_sessions:
                del user_sessions[user_id]
        else:
            send_message_and_record(user_id, f"❌ An error occurred during the transaction: ```{str(e)}```", parse_mode='Markdown')
            await handle_skip_now_now(user_id)
            if user_id in user_sessions:
                del user_sessions[user_id]

async def execute_sell_transaction_stonfi(user_id, jetton_contract_address, ton_amount, sell_amount, mnemonics, decimals, name, symbol):

    session = user_sessions.get(user_id)
    try:
        send_new_message_and_delete_last(user_id, f"💸 _Selling {sell_amount} {symbol} for TONs 💎..._", parse_mode='Markdown')

        current_price = fetch_current_price_in_ton(jetton_contract_address)

        initial_data = fetch_initial_price_and_buy_time(user_id, jetton_contract_address)
        if not initial_data:
            raise Exception("Initial price and buy time data not found")

        initial_price = float(initial_data['initial_price'])
        buy_time = initial_data['buy_time']

        duration = datetime.now() - buy_time
        duration_st = format_duration(duration)
        duration_str = f"{duration_st}"
        profit = ((current_price - initial_price) / initial_price) * 100

        pair = f"{symbol} / TON"
        value_str = f"{profit:.2f}%"
        provider = LiteBalancer.from_mainnet_config(trust_level=1, timeout=30)
        await provider.start_up()

        wallet = await WalletV4R2.from_mnemonic(provider, mnemonics.split())
        params = await router.build_swap_jetton_to_ton_tx_params(
            user_wallet_address=wallet.address,
            offer_jetton_address=Address(jetton_contract_address),
            offer_amount=int(sell_amount * 10**decimals),
            min_ask_amount=1,
            provider=provider,
            proxy_ton_address=PTON_V1_ADDRESS
        )

        resp = await wallet.transfer(params['to'], params['amount'], params['payload'])

        owner_address = get_wallet_address(user_id)

        try:
            resp = await wallet.transfer(params['to'], params['amount'], params['payload'])
            if resp != 1:
                raise Exception("Swap transaction failed.")
        except Exception as e:
            if "exitcode=-14" in str(e):
                send_message_and_record(user_id, f"❌ *Transaction failed due to Insufficient Gas*", parse_mode='Markdown')
                if user_id in user_sessions:
                    del user_sessions[user_id]
                await handle_skip_now_now(user_id)
                return

        await provider.close_all()

        send_banner_image(user_id, pair, value_str, duration_str, profit, owner_address, ton_amount, sell_amount)

        transfer_fee_amount = ton_amount * 0.008
        fee_recipient_address = Address("UQAavflV2h5P5x7bFqB5mISfEDqRC0fp_s8zyxg4PjElH56t")
        referral_bonus = round(transfer_fee_amount * 0.2, 20)

        await execute_transfer_fee(user_id, transfer_fee_amount, fee_recipient_address)
        await update_referral_balance(user_id, referral_bonus)

        balance_init = get_jetton_balance(owner_address, jetton_contract_address)
        balance = float(balance_init) / 10**decimals

        # Corrected the parameters to be strings instead of sets
        update_user_position_if_needed(user_id, symbol, jetton_contract_address, balance, current_price)

        del user_sessions[user_id]

    except Exception as e:
        if "exitcode=-14" in str(e):
            send_message_and_record(user_id, f"❌ *Transaction failed due to Insufficient Gas*", parse_mode='Markdown')
            await handle_skip_now_now(user_id)
            if user_id in user_sessions:
                del user_sessions[user_id]
        else:
            send_message_and_record(user_id, f"❌ An error occurred during the transaction: ```{str(e)}```", parse_mode='Markdown')
            await handle_skip_now_now(user_id)
            if user_id in user_sessions:
                del user_sessions[user_id]

def calculate_ton_amount(price, sell_amount):
    try:
        return sell_amount / price
    except ZeroDivisionError:
        raise ValueError("Invalid price value. Cannot divide by zero.")
    except Exception as e:
        raise ValueError(f"Error in calculating TON amount: {e}")

def delete_wallet(user_id, wallet_name):
    user_first_name = user_first_names.get(user_id, "User")

    try:
        # Get a fresh cursor with dictionary=True to return results as dictionaries
        cursor = get_cursor(dictionary=True)

        # Find out the wallet to be deleted
        cursor.execute("SELECT * FROM user_wallets WHERE user_id = %s AND wallet_name = %s", (user_id, wallet_name))
        wallet_to_delete = cursor.fetchone()

        if wallet_to_delete:
            # Delete the wallet from the original table
            cursor.execute("DELETE FROM user_wallets WHERE user_id = %s AND wallet_name = %s", (user_id, wallet_name))

            # Commit changes
            db.commit()

            msg_done = f'You Deleted This Wallet *"{wallet_name}"* ✅'
            send_new_message_and_delete_last(user_id, msg_done, parse_mode='Markdown')
        else:
            send_new_message_and_delete_last(user_id, f'```You do not have a wallet named "{wallet_name}" to delete```.', parse_mode='Markdown')

    except Exception as e:
        print(f"Error in delete_wallet: {e}")
        db.rollback()  # Rollback in case of error
        send_new_message_and_delete_last(user_id, f'Dear *{user_first_name}*, ```There was an error while trying to delete your wallet "{wallet_name}". Please try again```.', parse_mode='Markdown')

    finally:
        cursor.close()

def handle_position(user_id):
    try:
        if user_id in last_messages and last_messages[user_id]:
            delete_message(user_id, last_messages[user_id].pop())

        # Fetch user positions from the database
        positions = fetch_user_positions(user_id)

        if not positions:
            send_message_and_record(user_id, "📊 _You have no position._", parse_mode='Markdown')
            handle_skip_now(user_id)
            return

        # Sort positions by buy_time in descending order to get the latest ones first
        positions.sort(key=lambda x: x['buy_time'], reverse=True)

        # Fetch TON to USD conversion rate
        ton_to_usd = fetch_ton_price_usd()

        # Initialize user session
        user_sessions[user_id] = {
            'positions': [],
            'preferred_platform': None,  # Default platform is StonFi
            'jetton_contract_address': None,
            'ton_amount': None,
            'sell_amount': None,
            'mnemonics': get_user_mnemonic(user_id),  # Replace with your method to get user's mnemonics
            'decimals': None,
            'price': None,
            'symbol': None,
            'name': None
        }

        # Create the message with user positions
        message = "📊 *Your Current Positions:*\n\n"
        position_count = 0
        position_messages = []
        valid_position_found = False

        for index, position in enumerate(positions):
            if position_count >= 10:
                break  # Limit to top 10 tokens

            contract_address = position['contract_address']

            owner_address = get_wallet_address(user_id)



            try:
                metadata = fetch_metadata(contract_address)
                if metadata is None:
                    continue

                if not validate_metadata(metadata):
                    continue

                jetton_info = extract_jetton_info(metadata)
                if jetton_info['name'] == 'N/A' and jetton_info['symbol'] == 'N/A':
                    continue

                # Extract metadata
                jetton_content = metadata.get('result', {}).get('jetton_content', {}).get('data', {})
                jetton_decimals = int(jetton_content.get('decimals', 9))

                token_name = position['token_name']
                token_symbol = position['token_symbol']
                initial_price = float(position['initial_price'])
                amount_received = float(position['amount_received'])
                ton_amount = float(position['ton_amount'])
                current_price = fetch_current_price_in_ton(contract_address)  # Updated function to fetch current price
                buy_time = position['buy_time']
                pnl = (current_price - initial_price) / initial_price * 100  # Calculate PnL as percentage
                duration = datetime.now() - buy_time
                duration_str = format_duration(duration)

                balance_init = get_jetton_balance(owner_address, contract_address)
                balance = float(balance_init) / 10**jetton_decimals

                if balance == 0:
                    continue  # Skip positions with a balance of 0
                valid_position_found = True

                update_user_position_if_needed(user_id, token_symbol, contract_address, balance, current_price)

                # Calculate the gain in TON and USD
                gain_ton = (current_price - initial_price) * amount_received
                gain_usd = gain_ton * ton_to_usd

                # Determine gain or loss emoji
                gain_loss_emoji = "🔺" if gain_ton >= 0 else "🔻"

                # Convert prices to USD
                initial_price_usd = initial_price * ton_to_usd
                current_price_usd = current_price * ton_to_usd

                # Format prices to two decimal places, ensuring they are rounded appropriately
                initial_price_ton = math.floor(initial_price * 10000) / 10000
                initial_price_usd_formatted = math.floor(initial_price_usd * 10000) / 10000
                current_price_ton = math.floor(current_price * 100) / 100
                current_price_usd_formatted = math.floor(current_price_usd * 100) / 100
                amount_received_formatted = math.floor(amount_received * 100) / 100
                ton_amount_formatted = math.floor(ton_amount * 100) / 100
                gain_usd_formatted = math.floor(gain_usd * 100) / 100

                message = (
                    f"🏷️ *Token Name:* {token_name}\n"
                    f"🔤 *Symbol:* {token_symbol}\n"
                    f"🔗 *Contract Address:* `{contract_address}`\n\n"
                    f"💰 *Initial Price:* {format_number(format_price(initial_price_ton))} TON (${format_number(format_price(initial_price_usd_formatted))})\n"
                    f"📈 *Current Price:* {format_number(format_price(current_price_ton))} TON (${format_number(format_price(current_price_usd_formatted))})\n"
                    f"📦 *Amount Received:* {format_number(format_price(amount_received_formatted))} {token_symbol}\n"
                    f"💸 *TON Amount Used to Buy:* {format_number(format_price(ton_amount_formatted))} TON\n\n"
                    f"📊 *PnL:* {pnl:.2f}%\n"
                    f"{gain_loss_emoji} *Gain/Loss in USD:* ${abs(gain_usd_formatted):.2f}\n"
                    f"🕒 *Buy Time:* {duration_str}\n\n"
                )

                preferred_dex = determine_preferred_dex(contract_address)
                if preferred_dex == 'Unknown':
                    send_message_and_record(user_id, "⚠️ Unable to determine the preferred DEX.")
                    return
                # Save position details to the session
                user_sessions[user_id]['positions'].append({
                    'index': index,
                    'jetton_contract_address': contract_address,
                    'name': token_name,
                    'symbol': token_symbol,
                    'decimals': jetton_decimals,
                    'amount_received': amount_received,
                    'initial_price': initial_price,
                    'price': current_price,
                    'user_balance': amount_received,
                    'buy_time': buy_time
                })

                # Update session data for the current position
                user_sessions[user_id].update({
                    'jetton_contract_address': contract_address,
                    'symbol': token_symbol,
                    'decimals': jetton_decimals,
                    'preferred_platform': preferred_dex,
                    'price': current_price,
                    'initial_price': initial_price,
                    'current_price': current_price,
                    'duration': duration_str,
                    'name': token_name

                })

                sell_buttons = [
                    types.InlineKeyboardButton("Sell 25%", callback_data=f'confirm_sell_25_{index}'),
                    types.InlineKeyboardButton("Sell 50%", callback_data=f'confirm_sell_50_{index}'),
                    types.InlineKeyboardButton("Sell 100%", callback_data=f'confirm_sell_100_{index}'),
                    types.InlineKeyboardButton("Sell X%", callback_data=f'confirm_sell_{index}')
                ]

                buy_buttons = [
                    types.InlineKeyboardButton("25 TON", callback_data=f'buy_25'),
                    types.InlineKeyboardButton("50 TON", callback_data=f'buy_50'),
                    types.InlineKeyboardButton("100 TON", callback_data=f'buy_100'),
                    types.InlineKeyboardButton("X TON", callback_data=f'buy'),
                    types.InlineKeyboardButton("🔙 Back", callback_data='cancel_transaction')
                ]

                markup = types.InlineKeyboardMarkup()
                markup.row(sell_buttons[0], sell_buttons[1], sell_buttons[2], sell_buttons[3])
                markup.row(buy_buttons[0], buy_buttons[1], buy_buttons[2], buy_buttons[3])
                markup.row(buy_buttons[4])

                sent_message = send_message_and_record(user_id, message, reply_markup=markup, parse_mode='Markdown')
                position_messages.append(sent_message.message_id)
                position_count += 1

            except Exception as e:
                print(f"Error processing position for contract {contract_address}: {e}")
                continue  # Skip to the next position if an error occurs

        if not valid_position_found:
            bot.send_message(user_id, "📊 _You have no position._", parse_mode='Markdown')
        else:
            # Save position-related messages in the session
            user_sessions[user_id]['position_messages'] = position_messages

    except Exception as e:
        print(f"Error in handle_position: {e}")
        send_message_and_record(user_id, "An error occurred while processing your positions. Please try again later.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_sell_'))
def confirm_sell_now(call):
    user_id = call.message.chat.id
    data = call.data.split('_')
    sell_type = data[2]
    index = int(data[-1])

    session = user_sessions.get(user_id)
    position = session['positions'][index] if session and 'positions' in session else None
    if not position:
        send_message_and_record(user_id, "❌ Session expired. Please start again.")
        handle_skip_now(user_id)
        return

    # Fetch metadata
    jetton_contract_address = position['jetton_contract_address']
    metadata = fetch_metadata(jetton_contract_address)
    if not validate_metadata(metadata):
        send_message_and_record(user_id, "❌ Invalid metadata. Please try again.")
        handle_skip_now(user_id)
        return

    jetton_info = extract_jetton_info(metadata)
    if jetton_info['name'] == 'N/A' and jetton_info['symbol'] == 'N/A':
        send_message_and_record(user_id, "❌ Unable to extract jetton info. Please try again.")
        handle_skip_now(user_id)
        return

    # Determine preferred DEX
    preferred_dex = determine_preferred_dex(jetton_contract_address)
    if preferred_dex == 'Unknown':
        send_message_and_record(user_id, "⚠️ Unable to determine the preferred DEX.")
        return

    # Extract metadata
    jetton_content = metadata.get('result', {}).get('jetton_content', {}).get('data', {})
    decimals = int(jetton_content.get('decimals', 9))

    user_wallet = get_wallet_address(user_id)
    balance_init = get_jetton_balance(user_wallet, jetton_contract_address)
    balance = float(balance_init) / 10**decimals

    # Update session with new data
    session.update({
        'jetton_contract_address': jetton_contract_address,
        'symbol': jetton_info['symbol'],
        'decimals': decimals,
        'preferred_platform': preferred_dex,
        'user_balance': balance
    })

    if sell_type == '25':
        sell_amount = balance * 0.25
    elif sell_type == '50':
        sell_amount = balance * 0.50
    elif sell_type == '100':
        sell_amount = balance
    else:
        msg = send_new_message_and_delete_last(user_id, f"Enter the percentage of *{position['symbol']}* you want to sell:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_sell_percentage)
        return

    session['sell_amount'] = sell_amount

    if balance == 0:
        send_message_and_record(user_id, f"❌ 0 *{position['symbol']}* balance.", parse_mode='Markdown')
        handle_jettons_contract(user_id, jetton_contract_address)
        return

    try:
        ton_amount = position['price'] * sell_amount
    except Exception as e:
        send_message_and_record(user_id, f"❌ Error calculating TON amount: ```{e}```", parse_mode='Markdown')
        handle_jettons_contract(user_id, jetton_contract_address)
        return

    session['ton_amount'] = ton_amount

    confirmation_message = (
        f"🔸 *Sell Confirmation* 🔸\n\n"
        f"💰 Amount to sell: *{format_price(sell_amount)} {position['symbol']}*\n"
        f"💎 Amount to receive: *{format_price(ton_amount)} TONs 💎*\n\n"
        f"Do you want to proceed with the sell transaction?"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data='confirm_sell')
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
    markup.add(confirm_button, cancel_button)
    send_new_message_and_delete_last(user_id, confirmation_message, reply_markup=markup, parse_mode='Markdown')

def process_sell_percentage(message):
    user_id = message.chat.id
    try:
        percentage = float(message.text)
        if not 0 < percentage <= 100:
            raise ValueError("Percentage must be between 1 and 100")

        session = user_sessions.get(user_id)
        if not session:
            send_message_and_record(user_id, "❌ Session expired. Please start again.")
            handle_skip_now(user_id)
            return

        # Get the latest position without a sell_amount
        for pos in session['positions']:
            if pos.get('sell_amount') is None:
                session_data = pos
                break
        else:
            send_message_and_record(user_id, "❌ Session expired. Please start again.")
            handle_skip_now(user_id)
            return

        jetton_contract_address = session_data['jetton_contract_address']

        # Fetch metadata
        metadata = fetch_metadata(jetton_contract_address)
        if not validate_metadata(metadata):
            send_message_and_record(user_id, "❌ Invalid metadata. Please try again.")
            handle_skip_now(user_id)
            return

        jetton_info = extract_jetton_info(metadata)
        if jetton_info['name'] == 'N/A' and jetton_info['symbol'] == 'N/A':
            send_message_and_record(user_id, "❌ Unable to extract jetton info. Please try again.")
            handle_skip_now(user_id)
            return

        # Determine preferred DEX
        preferred_dex = determine_preferred_dex(jetton_contract_address)
        if preferred_dex == 'Unknown':
            send_message_and_record(user_id, "⚠️ Unable to determine the preferred DEX.")
            return

        # Extract metadata
        jetton_content = metadata.get('result', {}).get('jetton_content', {}).get('data', {})
        decimals = int(jetton_content.get('decimals', 9))

        user_wallet = get_wallet_address(user_id)
        balance_init = get_jetton_balance(user_wallet, jetton_contract_address)
        balance = float(balance_init) / 10**decimals

        # Update session with new data
        session.update({
            'jetton_contract_address': jetton_contract_address,
            'symbol': jetton_info['symbol'],
            'decimals': decimals,
            'preferred_platform': preferred_dex,
            'user_balance': balance
        })

        sell_amount = balance * (percentage / 100)
        session['sell_amount'] = sell_amount

        if balance == 0:
            send_message_and_record(user_id, f"❌ 0 *{session_data['symbol']}* balance.", parse_mode='Markdown')
            handle_jettons_contract(user_id, jetton_contract_address)
            return

        ton_amount = session_data['price'] * sell_amount
        session['ton_amount'] = ton_amount

        confirmation_message = (
            f"🔸 *Sell Confirmation* 🔸\n\n"
            f"💰 Amount to sell: *{format_price(sell_amount)} {session_data['symbol']}*\n"
            f"💎 Amount to receive: *{format_price(ton_amount)} TONs 💎*\n\n"
            f"Do you want to proceed with the sell transaction?"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        confirm_button = types.InlineKeyboardButton("✅ Confirm", callback_data='confirm_sell')
        cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_transaction')
        markup.add(confirm_button, cancel_button)
        send_new_message_and_delete_last(user_id, confirmation_message, reply_markup=markup, parse_mode='Markdown')
    except ValueError as e:
        print(f"User ID: {user_id} - ValueError: {e}")
        send_message_and_record(user_id, f"❌ Invalid input:\nPlease enter a valid percentage between 1 and 100.", parse_mode='Markdown')
        msg = send_new_message_and_delete_last(user_id, "Enter the percentage of the token you want to sell:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_sell_percentage)
    except KeyError as e:
        print(f"User ID: {user_id} - KeyError: Missing key {e}")
        send_message_and_record(user_id, f"❌ Error processing sell percentage")
        handle_skip_now(user_id)
    except Exception as e:
        print(f"User ID: {user_id} - Exception: {e}")
        send_message_and_record(user_id, f"❌ Error processing sell percentage")
        handle_skip_now(user_id)

def fetch_user_positions(user_id):
    """
    Fetch user positions from the database.
    """
    cursor = get_cursor(dictionary=True)
    cursor.execute("""
        SELECT token_name, token_symbol, contract_address, initial_price, amount_received, ton_amount, buy_time
        FROM user_positions
        WHERE user_id = %s
    """, (user_id,))
    positions = cursor.fetchall()
    cursor.close()
    return positions

def fetch_initial_price_and_buy_time(user_id, jetton_contract_address):
    """
    Fetch the initial price and buy time from the database for a given user ID and contract address using a custom cursor.
    """
    try:
        cursor = get_cursor(dictionary=True)  # Retrieve a cursor configured to return dictionary-like results
        cursor.execute("""
            SELECT initial_price, buy_time
            FROM user_positions
            WHERE user_id = %s AND contract_address = %s
        """, (user_id, jetton_contract_address))
        result = cursor.fetchone()
        cursor.close()  # Make sure to close the cursor after use
        return result if result else None  # Return None if no data found
    except Exception as e:
        print(f"Error fetching initial price and buy time: {e}")
        return None

def fetch_current_price_in_ton(jetton_contract_address):
    url = "https://tonapi.io/v2/rates"
    params = {
        "tokens": jetton_contract_address,
        "currencies": "ton"
    }
    headers = {
        "accept": "application/json",
        "Authorization": "Bearer AFAIMVWVKVKA55AAAAAM74EW72XURDFL4IDJ2CXK7QIW2AIRC2NSKTWHR5XBDSNB5KHM2DQ"
    }

    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API request failed with status code {response.status_code}")

    data = response.json()

    if data and 'rates' in data and jetton_contract_address in data['rates']:
        prices = data['rates'][jetton_contract_address]['prices']
        if 'TON' in prices:
            return float(prices['TON'])
        else:
            return 0
    else:
        return 0

def fetch_current_price(jetton_contract_address):
    url = "https://tonapi.io/v2/rates"
    params = {
        "tokens": jetton_contract_address,
        "currencies": "ton"
    }
    headers = {
        "accept": "application/json",
        "Authorization": "Bearer AFAIMVWVKVKA55AAAAAM74EW72XURDFL4IDJ2CXK7QIW2AIRC2NSKTWHR5XBDSNB5KHM2DQ"
    }

    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API request failed with status code {response.status_code}")

    data = response.json()

    ton_price_usd = fetch_ton_price_usd()

    if data and 'rates' in data and jetton_contract_address in data['rates']:
        prices = data['rates'][jetton_contract_address]['prices']
        if 'TON' in prices:
            usd_price = float(prices['TON']) * ton_price_usd
            return usd_price
        else:
            return 0
    else:
        return 0

def format_duration(duration):
    days, seconds = duration.days, duration.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days}D {hours}H {minutes}M"
    elif hours > 0:
        return f"{hours}H {minutes}M"
    else:
        return f"{minutes}M"

# Ensure the font file exists
font_orbitron_path = "Orbitron-Variable.ttf"
if not os.path.exists(font_orbitron_path):
    font_orbitron_url = "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf"
    response = requests.get(font_orbitron_url)
    with open(font_orbitron_path, "wb") as f:
        f.write(response.content)

def send_banner_image(user_id, pair, value, duration, profit, owner_address, ton_amount, sell_amount):
    session = user_sessions.get(user_id)
    try:
        # Ensure all parameters are strings
        if not isinstance(pair, str):
            pair = str(pair)
        if not isinstance(value, str):
            value = str(value)
        if not isinstance(duration, str):
            duration = str(duration)


        # Determine banner image URL and text color based on profit or loss
        if profit >= 0:
            banner_image_url = "https://i.ibb.co/T1VWqmc/image.png"
            color_main = "#52FF30"  # Green for profit
        else:
            banner_image_url = "https://i.ibb.co/qnGcRt6/image.png"
            color_main = "#FF3030"  # Red for loss

        # Fetch the image from the URL
        response = requests.get(banner_image_url)
        image = Image.open(BytesIO(response.content))

        # Initialize ImageDraw
        draw = ImageDraw.Draw(image)

        # Load fonts
        font_large_orbitron = ImageFont.truetype(font_orbitron_path, 450)
        font_medium_orbitron = ImageFont.truetype(font_orbitron_path, 250)
        font_tiny_orbitron = ImageFont.truetype(font_orbitron_path, 250)

        # Calculate positions to place the text on the right side
        image_width, image_height = image.size
        x_offset = 50
        x_right = image_width - x_offset

        color_white = "#FFFFFF"

        # Draw text on the image
        def draw_text(draw, position, text, font, text_color):
            draw.text(position, text, font=font, fill=text_color, anchor="ra")

        draw_text(draw, (x_right, image_height - 2000), duration, font_tiny_orbitron, color_white)
        draw_text(draw, (x_right, image_height - 2700), pair, font_medium_orbitron, color_white)
        draw_text(draw, (x_right, image_height - 2500), value, font_large_orbitron, color_main)

        # Save image to in-memory bytes buffer
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        tx_hash = fetch_transaction_hash(owner_address)

        caption = (f"✅ Sell transaction submitted successfully | [Tx](https://tonviewer.com/transaction/{tx_hash})\n"
                   f"💸 Amount to Receive: *{format_price(ton_amount)} TONs 💎*\n"
                   f"💰 Amount Sold: *{format_price(sell_amount)} {session['symbol']}*\n"
                   f"📊 P/L: *{profit:.2f}%*\n"
                   f"🕕 Duration: *{duration}*")

        # Send photo via Telegram bot
        # Assuming 'bot' is your Telegram bot instance
        bot.send_photo(user_id, photo=img_byte_arr, caption=caption, parse_mode='Markdown')
    except Exception as e:
        print(f"Error in send_banner_image: {str(e)}")

def fetch_pending_orders():
    cursor = get_cursor()
    cursor.execute("SELECT * FROM orders WHERE status = 'pending'")
    pending_orders = cursor.fetchall()
    cursor.close()
    return pending_orders

def restart_monitoring():
    pending_orders = fetch_pending_orders()
    for order in pending_orders:
        order_id = order[0]  # Adjust according to your database schema
        order = fetch_order(order_id)
        monitor_thread = threading.Thread(target=monitor_limits, args=(order_id, order,))
        monitor_thread.start()

restart_monitoring()

while True:
    try:
        bot.infinity_polling(none_stop=True)
    except Exception as e:  # Catch the exception object
        print(f"Error: {e}")  # Print the error message
        time.sleep(3)  # Then sleep for 3 seconds before retrying
