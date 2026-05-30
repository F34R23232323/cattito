# cattito - A Discord bot about catching cats.
# Copyright (C) 2026 Lia Milenakos & cattito Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import base64
import json
import random
from typing import Literal, Optional

type_dict = {
    "Fine": 1000, "Snacc": 900, "Nice": 800, "Good": 650, "Rare": 500,
    "Wild": 400, "Kittuh": 300, "Baby": 250, "Princess": 225, "Epic": 200,
    "Sus": 150, "Water": 120, "Brave": 100, "Unknown": 90, "Rickroll": 80,
    "Reverse": 60, "Superior": 45, "Trash": 35, "Legendary": 25, "Bloodmoon": 18,
    "Mythic": 15, "8bit": 12, "Corrupt": 10, "Professor": 8, "Rainbow": 6,
    "Divine": 5, "Space": 4, "Real": 3, "Ultimate": 2, "eGirl": 1, "eBoy": 0.5,
    "Angel": 0.1
}

cattypes = list(type_dict.keys())
cattype_lc_dict = {i.lower(): i for i in cattypes}

allowedemojis = [i.lower() + "cat" for i in cattypes]

pack_data = [
    {"name": "Wooden", "value": 65, "upgrade": 30, "totalvalue": 75, "special": False},
    {"name": "Stone", "value": 90, "upgrade": 30, "totalvalue": 100, "special": False},
    {"name": "Bronze", "value": 100, "upgrade": 30, "totalvalue": 130, "special": False},
    {"name": "Silver", "value": 115, "upgrade": 30, "totalvalue": 200, "special": False},
    {"name": "Gold", "value": 230, "upgrade": 30, "totalvalue": 400, "special": False},
    {"name": "Platinum", "value": 630, "upgrade": 30, "totalvalue": 800, "special": False},
    {"name": "Diamond", "value": 860, "upgrade": 30, "totalvalue": 1200, "special": False},
    {"name": "Celestial", "value": 2000, "upgrade": 0, "totalvalue": 2000, "special": False},
]

prism_names_start = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    "India", "Juliett", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa",
    "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey",
    "X-ray", "Yankee", "Zulu"
]
prism_names_end = [
    "", " Two", " Three", " Four", " Five", " Six", " Seven", " Eight",
    " Nine", " Ten", " Eleven", " Twelve", " Thirteen", " Fourteen",
    " Fifteen", " Sixteen", " Seventeen", " Eighteen", " Nineteen", " Twenty"
]
prism_names = []
for e in prism_names_end:
    for s in prism_names_start:
        prism_names.append(s + e)

NONOWORDS = [base64.b64decode(i).decode("utf-8") for i in ["bmlja2E=", "bmlja2Vy", "bmlnYQ==", "bmlnZ2E=", "bmlnZ2Vy"]]

vote_button_texts = [
    "You havent voted today!", "I know you havent voted ;)", "If vote cat will you friend :)",
    "Vote cat for president", "vote = 0.01% to escape basement", "vote vote vote vote vote",
    "mrrp mrrow go and vote now", "if you vote you'll be free (no)",
    "vote. btw, i have a pipebomb", "No votes? :megamind:", "Cat says you should vote",
    "cat will be happy if you vote", "VOTE NOW!!!!!", "I voted and got 1000000$",
    "I voted and found a gf", "lebron james forgot to vote", "vote if you like cats",
    "vote if cats > dogs", "you should vote for cat NOW!", "I'd vote if I were you",
]

hints = [
    "cattito has a wiki! <https://cattito.fun>",
    "cattito is open source! <https://github.com/F34R23232323/cattito>",
    "View all cats and rarities with /catalogue",
    "Unlike the normal one, Cat's /8ball isn't rigged",
    "/rate says /rate is 100% correct",
    "/casino is *surely* not rigged",
    "You probably shouldn't use a Discord bot for /remind-ers",
    "Cat /Rain is an excellent way to support development!",
    "cattito was made later than its support server",
    "cattito reached 100 servers 3 days after release",
    "Cat died for 2+ weeks bc the servers were flooded with water",
    "cattito's top.gg page was deleted at one point",
    "cattito has an official soundtrack! <https://youtu.be/Ww1opmRwYF0>",
    "4 with 832 zeros cats were deleted on September 5th, 2024",
    "Most cattito features were made within 2 weeks",
    "cattito was initially made for only one server",
    "cattito is made in Python with discord.py",
    "Discord didn't verify Cat properly the first time",
    "Looking at Cat's code won't make you regret your life choices!",
    "Cats aren't shared between servers to make it more fair and fun",
    "cattito can go offline! Don't panic if it does",
    "By default, cats spawn 1-10 minutes apart",
    "View the last catch as well as the next one with /last",
    "Make sure to leave cattito [a review on top.gg](<https://top.gg/bot/1387860417706987590#reviews>)!",
    "Rain minutes can be earned through battlepass and catnip!",
    "Reach catnip level 10 to get 5 bonus rain minutes!",
    "Every battlepass season grants free rain at level 30!",
]

news_list = [
    {"title": "Xyron Dev Moves to Hetzner!", "emoji": "💻"},
    {"title": "Mayor Whiskers Declares Nap Day", "emoji": "😸"},
    {"title": "Cattito's Kitten Parade Wows the Town", "emoji": "🎉"},
    {"title": "Mysterious Catnip Rain Hits the City", "emoji": "🌿"},
    {"title": "Cattito Opens the First Feline Café", "emoji": "☕"},
    {"title": "The Great Cat Tower Construction Begins", "emoji": "🏗️"},
    {"title": "Cattito Wins Best Purring Contest", "emoji": "🏆"},
    {"title": "Adventurous Cat Crew Explores the Attic", "emoji": "🕵️‍♂️"},
    {"title": "Cattito Paints a Giant Mural of Cats", "emoji": "🎨"},
    {"title": "Legend of the Midnight Mouse Solved", "emoji": "🌙"},
    {"title": "Cattito Throws the Biggest Catnip Party Ever", "emoji": "🎊"},
    {"title": "New Cat Hero Saves a Lost Kitten", "emoji": "🐾"},
    {"title": "Cattito Hosts a Fancy Cat Costume Ball", "emoji": "👑"},
    {"title": "Record-Breaking Catnap Marathon Achieved!", "emoji": "😴"},
    {"title": "Cattito Discovers Magical Fish Pond", "emoji": "🐟"},
    {"title": "New Commands Drop!", "emoji": "🐾"},
]

funny = [
    "why did you click this this arent yours", "absolutely not",
    "cattito not responding, try again later", "you cant", "can you please stop",
    "try again", "403 not allowed", "stop", "get a life", "not for you",
    "no", "nuh uh", "access denied", "forbidden", "don't do this",
    "cease", "wrong", "aw dangit", "why don't you press buttons from your commands",
    "you're only making me angrier", "why are you like this",
    "legends say you get something for clicking it 1000 times",
]

rain_shill = "⭐ Try /rain to start a cat rain!"

VIEW_TIMEOUT = 86400

total_commands_used = 0

try:
    with open("config/aches.json", "r") as f:
        ach_list = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    ach_list = {}

try:
    with open("config/battlepass.json", "r", encoding="utf-8") as f:
        battle = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    battle = {"quests": {"vote": {}, "catch": {}, "misc": {}, "extra1": {}, "extra2": {}}, "seasons": {}}

try:
    with open("config/catnip.json", "r", encoding="utf-8") as f:
        catnip_list = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    catnip_list = {"levels": {}, "perks": {}, "quotes": {}}

try:
    with open("facts.txt") as f:
        cat_facts_list = f.read().split("\n")
except FileNotFoundError:
    cat_facts_list = []

ach_names = ach_list.keys()
ach_titles = {value["title"].lower(): key for key, value in ach_list.items()}

testers = [
    1296592197260415057,
    1075077561454973020,
    952009664600608808,
    579080596723335181,
]

EXTRA_QUEST_TRIGGERS = {
    "casino_spins": "casino_spin", "slots_winner": "slots_win",
    "roulette_gambler": "roulette_spin", "dice_roller": "roll",
    "lucky_pig": "pig", "fortune_teller": "catball",
    "game_master": "rate", "strategic_mind": "ttc",
    "big_spender": "roulette_spin", "blackjack_master": "slots_bigwin",
    "dice_enthusiast": "roll", "roulette_champion": "roulette",
    "pig_pro": "pig50", "fortune_seeker": "catball",
    "gaming_legend": "any_game", "coin_flipper": "coinflip",
    "lucky_flip": "coinflip_win", "quiz_starter": "quiz_correct",
    "quiz_master": "quiz_correct",
    "gifter": "gift", "trader": "trade",
    "prism_crafter": "prism", "pack_opener": "pack_open",
    "rain_starter": "rain_start", "fact_collector": "fact",
    "cookie_clicker": "cookie", "commander": "ping",
    "definition_seeker": "define", "news_reader": "news",
    "random_lover": "random", "reminder_setter": "reminder",
    "generous_gifter": "gift", "master_trader": "trade",
    "collector_supreme": "pack_open", "quiz_scholar": "quiz_complete",
    "flipper": "coinflip",
}

CAT_TRIVIA = [
    {"q": "How many hours a day do cats sleep on average?", "a": "13", "choices": ["8", "13", "20", "5"], "fun": "Cats are professional nappers — up to 16h on a lazy day!"},
    {"q": "What is a group of cats called?", "a": "clowder", "choices": ["pride", "clowder", "pack", "herd"], "fun": "A group of kittens is called a kindle!"},
    {"q": "How many toes does a typical cat have?", "a": "18", "choices": ["16", "18", "20", "14"], "fun": "Polydactyl cats can have even more!"},
    {"q": "What is the fastest domestic cat breed?", "a": "Egyptian Mau", "choices": ["Siamese", "Bengal", "Egyptian Mau", "Abyssinian"], "fun": "Egyptian Maus can run at 30mph!"},
    {"q": "Cats have how many whiskers on average?", "a": "24", "choices": ["12", "18", "24", "32"], "fun": "Whiskers help cats judge tight spaces!"},
    {"q": "What is a female cat called?", "a": "queen", "choices": ["doe", "queen", "hen", "cow"], "fun": "Male cats are called toms!"},
    {"q": "Which sense is weakest in cats?", "a": "taste", "choices": ["smell", "hearing", "sight", "taste"], "fun": "Cats can't taste sweetness at all!"},
    {"q": "How many distinct sounds can cats make?", "a": "100", "choices": ["16", "50", "100", "200"], "fun": "Dogs make about 10 sounds by comparison!"},
    {"q": "What percentage of their lives do cats spend grooming?", "a": "30%", "choices": ["10%", "20%", "30%", "50%"], "fun": "Grooming also keeps them cool!"},
    {"q": "Cats walk like which other animal?", "a": "camel", "choices": ["horse", "dog", "camel", "giraffe"], "fun": "Both move both legs on one side at a time — 'pacing gait'!"},
    {"q": "What is the oldest known pet cat? (years)", "a": "9500", "choices": ["4000", "9500", "2000", "15000"], "fun": "Found in a Cyprus grave dating to ~7500 BC!"},
    {"q": "A cat's heart beats how many times per minute?", "a": "140", "choices": ["70", "100", "140", "200"], "fun": "That's about twice as fast as a human heart!"},
    {"q": "Cats can jump how many times their height?", "a": "6", "choices": ["3", "6", "10", "15"], "fun": "That's equivalent to a human jumping over a bus!"},
    {"q": "What is the name of the reflex that makes cats land on their feet?", "a": "righting reflex", "choices": ["balance reflex", "righting reflex", "gravity reflex", "paw reflex"], "fun": "Kittens develop this by 3 weeks old!"},
    {"q": "How many muscles does each cat ear have?", "a": "32", "choices": ["6", "16", "32", "48"], "fun": "This lets cats rotate their ears 180 degrees!"},
    {"q": "What colour are all kittens' eyes at birth?", "a": "blue", "choices": ["brown", "green", "blue", "grey"], "fun": "Permanent eye colour develops at 6-7 weeks!"},
    {"q": "Which country has the most pet cats per capita?", "a": "Russia", "choices": ["USA", "Japan", "Russia", "France"], "fun": "About 57% of Russian households have a cat!"},
    {"q": "A cat's nose print is unique like what human feature?", "a": "fingerprint", "choices": ["ear shape", "fingerprint", "iris", "tongue"], "fun": "No two cats share the same nose print pattern!"},
    {"q": "How many teeth does an adult cat have?", "a": "30", "choices": ["26", "28", "30", "32"], "fun": "Humans have 32 — cats have fewer but sharper!"},
    {"q": "What is the loudest cat breed?", "a": "Siamese", "choices": ["Maine Coon", "Bengal", "Siamese", "Burmese"], "fun": "Siamese cats are famously chatty and vocal!"},
]
