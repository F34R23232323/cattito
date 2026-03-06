#!/usr/bin/env python3
"""
Run this script against your main.py to remove all Valentine's content:
    python3 remove_valentines.py main.py
"""

import re
import sys

def apply_changes(source):
    original_len = len(source)
    changes_made = []

    # 1. Remove Valentine pack from pack_data
    old = '    {"name": "Valentine", "value": 3000, "upgrade": 1000, "totalvalue": 5000, "special": True},\n'
    if old in source:
        source = source.replace(old, '')
        changes_made.append("Removed Valentine pack from pack_data")

    # 2. Replace rain_shill
    old = 'rain_shill = "\U0001f49d Valentine\'s Sale! -20% /rain"'
    new = 'rain_shill = "\u2b50 Try /rain to start a cat rain!"'
    if old in source:
        source = source.replace(old, new)
        changes_made.append("Replaced rain_shill text")

    # 3. Remove valentine pack award in progress() vote section
    old = (
        '        user.pack_valentine += 1\n'
        '        if user.valentine_user:\n'
        '            valentine_user = await Profile.get_or_create(user_id=user.valentine_user, guild_id=user.guild_id)\n'
        '            valentine_user.pack_valentine += 1\n'
        '            await valentine_user.save()\n'
        '\n'
        '        current_xp = user.progress + user.vote_reward'
    )
    new = '        current_xp = user.progress + user.vote_reward'
    if old in source:
        source = source.replace(old, new)
        changes_made.append("Removed valentine pack award in vote progress()")

    # 4. Remove valentine event text from progress_embed()
    old = (
        '    if "top.gg" in quest_data[\'title\']:\n'
        '        streak_reward += f"\\n\U0001f49d **Valentine\'s Event!** +1 {get_emoji(\'valentinepack\')} Valentine pack!"\n'
        '        if not user.valentine_user:\n'
        '            streak_reward += "\\n\U0001f494 find a /valentine - both get a pack when either votes!"\n'
        '        else:\n'
        '            streak_reward += f"\\n\U0001f49e and +1 {get_emoji(\'valentinepack\')} for your valentine!"\n'
    )
    if old in source:
        source = source.replace(old, '')
        changes_made.append("Removed valentine event text from progress_embed()")

    # 5. Remove VALENTINES catch block
    # Use regex for robustness
    pattern = r'                # VALENTINES .*?                    await valentine_user\.save\(\)\n'
    match = re.search(pattern, source, re.DOTALL)
    if match:
        source = source[:match.start()] + source[match.end():]
        changes_made.append("Removed VALENTINES catch block")

    # 6. Replace valentines rain shill in catch
    old = '                    suffix_string += f"\\n\U0001f49d valentines sale! -20% </rain:{RAIN_ID}>"'
    new = '                    suffix_string += f"\\n\u2614 Try </rain:{RAIN_ID}> to start a cat rain!"'
    if old in source:
        source = source.replace(old, new)
        changes_made.append("Replaced valentines rain shill in catch")

    # 7. Remove /valentine command
    pattern = r'@bot\.tree\.command\(description="will u\.\.\. be my valentine\?~ .*?allowed_mentions=discord\.AllowedMentions\(users=True\)\n    \)\n'
    match = re.search(pattern, source, re.DOTALL)
    if match:
        source = source[:match.start()] + source[match.end():]
        changes_made.append("Removed /valentine command")

    # 8. Remove valentine pack in vote webhook handler (recieve_vote)
    old = (
        '    user.pack_valentine += 1\n'
        '    if user.valentine_user:\n'
        '        valentine_user = await Profile.get_or_create(user_id=user.valentine_user, guild_id=user.guild_id)\n'
        '        valentine_user.pack_valentine += 1\n'
        '        await valentine_user.save()\n'
    )
    if old in source:
        source = source.replace(old, '')
        changes_made.append("Removed valentine pack in recieve_vote webhook")

    # 9. Remove valentine event lines in battlepass gen_main() vote section
    old = '        if "top.gg" in quest_data[\'title\']:\n'
    # Only remove the valentine-specific part inside this section (in battlepass)
    # The battlepass section adds valentine event lines - use a targeted replacement
    old_battle_valentine = (
        '            description += f"- Reward: {user.vote_reward} XP"\n'
        '\n'
        '            next_streak_data = get_streak_reward(global_user.vote_streak + 1)\n'
        '            if next_streak_data["reward"] and global_user.vote_time_topgg + 24 * 3600 > time.time():\n'
        '                description += f" + {next_streak_data[\'emoji\']} 1 {next_streak_data[\'reward\'].capitalize()} pack"\n'
        '\n'
        '            description += f"{streak_string}\\n"\n'
    )
    # This one might just be fine as-is since it doesn't add valentine content by itself
    # The valentine addition was: streak_reward += valentine stuff (which we removed in change 4)

    print(f"\nChanges applied: {len(changes_made)}")
    for c in changes_made:
        print(f"  + {c}")
    print(f"\nSize: {original_len} -> {len(source)} chars ({original_len - len(source)} removed)")
    return source


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 remove_valentines.py main.py")
        sys.exit(1)

    fname = sys.argv[1]
    with open(fname, 'r', encoding='utf-8') as f:
        source = f.read()

    result = apply_changes(source)

    out_fname = fname.replace('.py', '_no_valentines.py')
    with open(out_fname, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"\nOutput written to: {out_fname}")