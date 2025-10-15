"""
FAIL-SAFE RestaurantJi Scraper

Features:
- Saves after each restaurant (no data loss)
- Can resume from where it left off
- Skips already-scraped restaurants
- Creates timestamped backups
- Detailed progress tracking
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
from difflib import SequenceMatcher
import os
from datetime import datetime
import json


class FailSafeScraper:
    """Scraper with progressive saving and resume capability"""
    
    def __init__(self, output_file="restaurant_comments.csv", 
                 progress_file="scraper_progress.json"):
        self.output_file = output_file
        self.progress_file = progress_file
        self.scraped_restaurants = set()
        
        # Load progress if exists
        self._load_progress()
    
    def _load_progress(self):
        """Load which restaurants have already been scraped"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)
                    self.scraped_restaurants = set(progress.get('scraped', []))
                print(f"📂 Loaded progress: {len(self.scraped_restaurants)} restaurants already scraped")
            except Exception as e:
                print(f"⚠️  Could not load progress file: {e}")
                self.scraped_restaurants = set()
    
    def _save_progress(self, restaurant_query):
        """Save progress after each restaurant"""
        self.scraped_restaurants.add(restaurant_query)
        
        try:
            with open(self.progress_file, 'w') as f:
                json.dump({
                    'scraped': list(self.scraped_restaurants),
                    'last_update': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save progress: {e}")
    
    def _save_data(self, new_data, restaurant_query):
        """
        Save data progressively - appends to CSV after each restaurant
        Also creates a timestamped backup
        """
        if not new_data:
            return
        
        # Convert to DataFrame
        df_new = pd.DataFrame(new_data)
        
        # Append to main file (or create if doesn't exist)
        if os.path.exists(self.output_file):
            # Append to existing
            df_new.to_csv(self.output_file, mode='a', header=False, index=False)
            print(f"   💾 Appended {len(df_new)} rows to {self.output_file}")
        else:
            # Create new
            df_new.to_csv(self.output_file, mode='w', header=True, index=False)
            print(f"   💾 Created {self.output_file} with {len(df_new)} rows")
        
        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backups/backup_{timestamp}_{restaurant_query.replace(' ', '_')}.csv"
        df_new.to_csv(backup_file, index=False)
        print(f"   💾 Backup saved: {backup_file}")
    
    def is_already_scraped(self, restaurant_query):
        """Check if restaurant was already scraped"""
        return restaurant_query.lower() in [r.lower() for r in self.scraped_restaurants]
    
    def calculate_match_score(self, query, restaurant_name):
        """Calculate how well names match (0.0-1.0)"""
        return SequenceMatcher(None, query.lower(), restaurant_name.lower()).ratio()
    
    def scrape_restaurant(self, query, location="Austin, TX", show_browser=False, 
                         min_match_score=0.6):
        """
        Scrape a restaurant's comments with fail-safe features
        """
        print(f"\n{'='*70}")
        print(f"🔍 Processing: {query}")
        print(f"{'='*70}")
        
        # Check if already scraped
        if self.is_already_scraped(query):
            print(f"✅ Already scraped! Skipping '{query}'")
            return []
        
        # Setup Chrome
        options = Options()
        if not show_browser:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        
        if show_browser:
            print("🔍 Browser window will open - watch the scraping in action!")
        
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            print(f"❌ Error: Could not start Chrome. Make sure Chrome is installed.")
            print(f"   {e}")
            return []
        
        try:
            # Search for restaurant
            search_url = f"https://www.restaurantji.com/search/?query={query.replace(' ', '+')}&place={location.replace(' ', '+')}"
            print(f"🔍 Searching: {search_url}")
            
            driver.get(search_url)
            time.sleep(3)
            
            # Parse search results
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            all_links = soup.find_all('a', href=True)
            restaurant_links = []
            
            for link in all_links:
                href = link.get('href', '')
                if href.count('/') == 4 and href.startswith('/') and href.endswith('/'):
                    name = link.get_text(strip=True)
                    if name:
                        score = self.calculate_match_score(query, name)
                        restaurant_links.append({
                            'name': name,
                            'url': 'https://www.restaurantji.com' + href,
                            'score': score
                        })
            
            if not restaurant_links:
                print(f"❌ No restaurants found for '{query}'")
                return []
            
            # Sort by match score
            restaurant_links.sort(key=lambda x: x['score'], reverse=True)
            best_match = restaurant_links[0]
            
            print(f"✓ Best match: {best_match['name']} (score: {best_match['score']:.2f})")
            
            # Check match score
            if best_match['score'] < min_match_score:
                print(f"⚠️  Low match score ({best_match['score']:.2f} < {min_match_score})")
                print(f"   Found: '{best_match['name']}'")
                print(f"   Looking for: '{query}'")
                print(f"   Skipping to avoid false match")
                return []
            
            # Get comments
            comments_url = best_match['url'] + 'comments/'
            print(f"📝 Fetching comments: {comments_url}")
            
            driver.get(comments_url)
            time.sleep(3)
            
            # Parse comments
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            comment_elements = soup.find_all(class_='comment-content')
            
            results = []
            for elem in comment_elements:
                comment_html = str(elem)
                comment_text = elem.get_text(strip=True)
                
                if comment_text:
                    results.append({
                        'input_query': query,
                        'restaurant_name': best_match['name'],
                        'restaurant_url': best_match['url'],
                        'match_score': best_match['score'],
                        'comment_html': comment_html,
                        'comment_text': comment_text,
                        'scraped_at': datetime.now().isoformat()
                    })
            
            print(f"✓ Found {len(results)} comments")
            
            # SAVE IMMEDIATELY after each restaurant
            if results:
                self._save_data(results, query)
                self._save_progress(query)
                print(f"✅ Data saved successfully for '{query}'")
            
            return results
            
        except Exception as e:
            print(f"❌ Error scraping '{query}': {e}")
            import traceback
            traceback.print_exc()
            
            # Even if error, save what we have
            print(f"⚠️  Restaurant '{query}' failed - moving to next one")
            return []
            
        finally:
            driver.quit()
    
    def scrape_multiple(self, restaurants, location="Austin, TX", 
                       show_browser=False, delay=3, min_match_score=0.6):
        """
        Scrape multiple restaurants with fail-safe features
        """
        print(f"\n{'#'*70}")
        print(f"🍽️  FAIL-SAFE SCRAPER")
        print(f"{'#'*70}")
        print(f"Total restaurants: {len(restaurants)}")
        print(f"Already scraped: {len(self.scraped_restaurants)}")
        print(f"To scrape: {len([r for r in restaurants if not self.is_already_scraped(r)])}")
        print(f"Output file: {self.output_file}")
        print(f"Progress file: {self.progress_file}")
        print(f"{'#'*70}\n")
        
        successful = 0
        failed = 0
        skipped = 0
        
        for i, restaurant in enumerate(restaurants, 1):
            print(f"\n{'='*70}")
            print(f"Restaurant {i}/{len(restaurants)}")
            print(f"{'='*70}")
            
            if self.is_already_scraped(restaurant):
                skipped += 1
                continue
            
            try:
                results = self.scrape_restaurant(
                    query=restaurant,
                    location=location,
                    show_browser=show_browser,
                    min_match_score=min_match_score
                )
                
                if results:
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                failed += 1
                print(f"❌ Fatal error with '{restaurant}': {e}")
            
            # Wait between restaurants
            if i < len(restaurants):
                print(f"\n⏳ Waiting {delay} seconds before next restaurant...")
                time.sleep(delay)
        
        # Final summary
        print(f"\n{'='*70}")
        print(f"FINAL SUMMARY")
        print(f"{'='*70}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️  Skipped (already done): {skipped}")
        print(f"📁 Total in database: {len(self.scraped_restaurants)}")
        
        if os.path.exists(self.output_file):
            df = pd.read_csv(self.output_file)
            print(f"\n📊 Total comments in {self.output_file}: {len(df)}")
            print(f"📊 Unique restaurants: {df['restaurant_name'].nunique()}")
            print(f"\n💾 All data saved to: {self.output_file}")
        
        print(f"{'='*70}")
    
    def reset_progress(self):
        """Reset progress - use if you want to re-scrape everything"""
        if os.path.exists(self.progress_file):
            os.remove(self.progress_file)
            print(f"✓ Progress reset - will re-scrape all restaurants")
        self.scraped_restaurants = set()


def main():
    """Main function with fail-safe features"""
    
    print("\n" + "🍽️ "*25)
    print()
    
    # ========================================
    # CONFIGURATION
    # ========================================
    
    restaurants_to_scrape = pd.read_csv('rest-to-scrape.csv')["name"].tolist()
    
    location = "Austin, TX"
    show_browser = False
    delay_between = 3
    min_match_score = 0.6
    
    output_file = "restaurant_comments.csv"
    progress_file = "scraper_progress.json"
    
    # ========================================
    
    # Create fail-safe scraper
    scraper = FailSafeScraper(
        output_file=output_file,
        progress_file=progress_file
    )
    
    # Optional: Reset progress (uncomment to start fresh)
    # scraper.reset_progress()
    
    # Scrape with fail-safe features
    scraper.scrape_multiple(
        restaurants=restaurants_to_scrape,
        location=location,
        show_browser=show_browser,
        delay=delay_between,
        min_match_score=min_match_score
    )
    
    print("\n" + "🍽️ "*25)
    print("\n✨ Done! Check your CSV file. ✨")
    print("\n💡 TIP: If the script crashed, just run it again!")
    print("   It will automatically skip already-scraped restaurants.\n")


if __name__ == "__main__":
    main()
