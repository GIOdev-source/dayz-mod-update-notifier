#!/usr/bin/env python3
"""
DayZ Mod Update Notifier for GTX Gaming Server
Monitors Steam Workshop mods for updates and sends Discord notifications
Author: Your Name
Date: October 6, 2025
"""

import requests
import json
import time
import os
from datetime import datetime
import sqlite3
import sys

class DayZModNotifier:
    def __init__(self, discord_webhook_url, steam_api_key):
        self.discord_webhook_url = discord_webhook_url
        self.steam_api_key = steam_api_key
        self.db_file = "mod_updates.db"
        self.init_database()
        
        # Your server mod IDs
        self.mod_ids = [
            "2579252958", "3413364741", "2628707698", "1710977250", "2794690371",
            "2705731852", "1565871491", "1932611410", "3353822981", "1559212036",
            "2851058261", "3347202534", "1646187754", "1564026768", "2810212624",
            "3071767590", "3051379451", "2545327648", "2794626429", "1750506510",
            "2714183642", "2931436407", "2246697421", "2428595209", "3487506464",
            "2903723881", "2181531192", "2601606391", "1964490092", "3495385414",
            "3494856709", "3577460706", "3483591601", "3483631928", "3483633965",
            "3566588945", "3492829525", "3485866845", "3520324415", "3495004422",
            "3440974241", "3452063031", "3049835903", "3419019141", "3007376094",
            "2663169692", "2299460322", "2913803769", "3390675689", "3219973018",
            "2842779598", "2007900691", "3332001143", "2878980498", "3310715247",
            "3117613872", "2879070654", "2692979668", "2848159851", "3528780688",
            "2936585965", "2443122116", "3439337803", "2458896948", "1828439124",
            "1797720064", "3017273820", "3036319373"
        ]

    def init_database(self):
        """Initialize SQLite database to track mod update times"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mod_updates (
                mod_id TEXT PRIMARY KEY,
                last_updated INTEGER,
                mod_name TEXT,
                last_checked INTEGER
            )
        ''')
        conn.commit()
        conn.close()

    def get_mod_info(self, mod_ids_batch):
        """Get mod information from Steam API"""
        url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
        
        data = {
            'key': self.steam_api_key,
            'itemcount': len(mod_ids_batch),
            'format': 'json'
        }
        
        for i, mod_id in enumerate(mod_ids_batch):
            data[f'publishedfileids[{i}]'] = mod_id
        
        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching mod info: {e}")
            return None

    def check_for_updates(self):
        """Check all mods for updates"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        updated_mods = []
        
        # Process mods in batches of 100 (Steam API limit)
        batch_size = 100
        for i in range(0, len(self.mod_ids), batch_size):
            batch = self.mod_ids[i:i + batch_size]
            mod_data = self.get_mod_info(batch)
            
            if not mod_data or 'response' not in mod_data:
                continue
                
            for file_details in mod_data['response']['publishedfiledetails']:
                if file_details['result'] != 1:  # Success
                    continue
                    
                mod_id = file_details['publishedfileid']
                mod_name = file_details.get('title', f'Mod {mod_id}')
                last_updated = file_details.get('time_updated', 0)
                
                # Check if mod exists in database
                cursor.execute('SELECT last_updated FROM mod_updates WHERE mod_id = ?', (mod_id,))
                result = cursor.fetchone()
                
                if result is None:
                    # New mod, add to database
                    cursor.execute('''
                        INSERT INTO mod_updates (mod_id, last_updated, mod_name, last_checked)
                        VALUES (?, ?, ?, ?)
                    ''', (mod_id, last_updated, mod_name, int(time.time())))
                    print(f"Added new mod to tracking: {mod_name}")
                    
                elif result[0] < last_updated:
                    # Mod has been updated
                    cursor.execute('''
                        UPDATE mod_updates 
                        SET last_updated = ?, mod_name = ?, last_checked = ?
                        WHERE mod_id = ?
                    ''', (last_updated, mod_name, int(time.time()), mod_id))
                    
                    updated_mods.append({
                        'id': mod_id,
                        'name': mod_name,
                        'updated': datetime.fromtimestamp(last_updated).strftime('%Y-%m-%d %H:%M:%S'),
                        'url': f'https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}'
                    })
                    
                else:
                    # Update last checked time
                    cursor.execute('''
                        UPDATE mod_updates 
                        SET last_checked = ?
                        WHERE mod_id = ?
                    ''', (int(time.time()), mod_id))
            
            # Small delay between batches to avoid rate limiting
            time.sleep(1)
        
        conn.commit()
        conn.close()
        
        return updated_mods

    def send_discord_notification(self, updated_mods):
        """Send Discord notification about updated mods"""
        if not updated_mods:
            return
            
        embed = {
            "title": "🔄 DayZ Server Mod Updates Detected!",
            "description": f"**{len(updated_mods)} mod(s) have been updated**",
            "color": 0x00ff00,  # Green color
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "GTX Gaming DayZ Server Monitor"
            },
            "fields": []
        }
        
        for mod in updated_mods[:10]:  # Limit to 10 mods to avoid embed limits
            embed["fields"].append({
                "name": f"📦 {mod['name']}",
                "value": f"**Updated:** {mod['updated']}\n**ID:** `{mod['id']}`\n[View on Workshop]({mod['url']})",
                "inline": True
            })
        
        if len(updated_mods) > 10:
            embed["fields"].append({
                "name": "➕ Additional Updates",
                "value": f"And {len(updated_mods) - 10} more mods were updated.",
                "inline": False
            })
        
        # Add warning about server restart
        embed["fields"].append({
            "name": "⚠️ Action Required",
            "value": "Your GTX Gaming server may need to be restarted to apply these mod updates.",
            "inline": False
        })
        
        payload = {
            "embeds": [embed],
            "content": "@here Mod updates detected for DayZ server!"
        }
        
        try:
            response = requests.post(self.discord_webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"Discord notification sent for {len(updated_mods)} updated mods")
        except requests.RequestException as e:
            print(f"Error sending Discord notification: {e}")

    def run_check(self):
        """Run a single check for mod updates"""
        print(f"Checking for mod updates at {datetime.now()}")
        updated_mods = self.check_for_updates()
        
        if updated_mods:
            print(f"Found {len(updated_mods)} updated mods:")
            for mod in updated_mods:
                print(f"  - {mod['name']} (ID: {mod['id']})")
            self.send_discord_notification(updated_mods)
        else:
            print("No mod updates found")

    def run_monitor(self, check_interval=3600):  # Default: check every hour
        """Run continuous monitoring"""
        print("Starting DayZ mod update monitor...")
        print(f"Monitoring {len(self.mod_ids)} mods")
        print(f"Check interval: {check_interval} seconds")
        
        while True:
            try:
                self.run_check()
                print(f"Next check in {check_interval} seconds...")
                time.sleep(check_interval)
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                break
            except Exception as e:
                print(f"Error during monitoring: {e}")
                print("Continuing in 60 seconds...")
                time.sleep(60)

def main():
    """Main function"""
    # Configuration
    DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1424699281352163390/62VXQ3nus7y7TEt8sdw6Ltt2sWgHyLoiC6quzXovY1g_kg7h0be-BHD3jN3Yg6HlXr5I"
    STEAM_API_KEY = "FB4A48C58C7778630BFDE1A9D5F5A94A"
    
    # Create notifier instance
    notifier = DayZModNotifier(DISCORD_WEBHOOK_URL, STEAM_API_KEY)
    
    # Choose mode: single check or continuous monitoring
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        notifier.run_check()
    else:
        # Run continuous monitoring (check every hour)
        notifier.run_monitor(3600)

if __name__ == "__main__":
    main()