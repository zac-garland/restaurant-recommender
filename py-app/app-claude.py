"""
RestaurantAI - Enhanced with Photo Gallery & Smart Score
Implements: TF-IDF, BERT, Sentiment Analysis, Topic Modeling, Smart Scoring System
"""

from shiny import App, ui, render, reactive
import pandas as pd
import numpy as np
import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
import plotly.graph_objects as go
import plotly.express as px
import os
from datetime import datetime
import pytz
from transformers import pipeline
from sentence_transformers import SentenceTransformer
import warnings
from dotenv import load_dotenv 
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# You'll need to set this environment variable with your Google Places API key
GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')

# ============================================================================
# DATA LOADING & PREPROCESSING
# ============================================================================

def load_data():
    """Load data from SQLite database including photos"""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'austin_restaurants.db')
    conn = sqlite3.connect(db_path)
    
    try:
        # Load restaurants with place details
        restaurants_query = """
        SELECT 
            r.id,
            r.name,
            r.address,
            r.rating,
            r.price_level,
            r.user_ratings_total,
            r.lat,
            r.lng,
            r.place_tags as cuisine,
            COALESCE(pd.serves_vegetarian_food, 0) as serves_vegetarian,
            COALESCE(pd.dine_in, 0) as dine_in,
            COALESCE(pd.takeout, 0) as takeout,
            COALESCE(pd.delivery, 0) as delivery,
            COALESCE(pd.serves_beer, 0) as serves_beer,
            COALESCE(pd.serves_wine, 0) as serves_wine,
            COALESCE(pd.serves_breakfast, 0) as serves_breakfast,
            COALESCE(pd.serves_brunch, 0) as serves_brunch,
            COALESCE(pd.serves_lunch, 0) as serves_lunch,
            COALESCE(pd.serves_dinner, 0) as serves_dinner,
            pd.website,
            pd.formatted_phone_number,
            pd.open_times
        FROM restaurants r
        LEFT JOIN place_details pd ON r.id = pd.id
        WHERE r.business_status = 'OPERATIONAL'
        """
        restaurants = pd.read_sql_query(restaurants_query, conn)
        
        # Load reviews
        reviews_query = """
        SELECT 
            id as restaurant_id,
            author_name as author,
            author_url,
            profile_photo_url,
            rating,
            text,
            time
        FROM reviews
        WHERE text IS NOT NULL AND text != ''
        """
        reviews = pd.read_sql_query(reviews_query, conn)
        reviews['time'] = pd.to_datetime(reviews['time'], unit='s')
        
        # Load photos
        photos_query = """
        SELECT 
            id as restaurant_id,
            photo_reference,
            width,
            height,
            html_attributions
        FROM photos
        """
        photos = pd.read_sql_query(photos_query, conn)
        
        # Convert boolean columns
        bool_cols = ['serves_vegetarian', 'dine_in', 'takeout', 'delivery', 
                     'serves_beer', 'serves_wine', 'serves_breakfast', 
                     'serves_brunch', 'serves_lunch', 'serves_dinner']
        for col in bool_cols:
            if col in restaurants.columns:
                restaurants[col] = restaurants[col].astype(bool)
        
        restaurants['outdoor_seating'] = False
        
        print(f"Loaded {len(restaurants)} restaurants, {len(reviews)} reviews, {len(photos)} photos")
        
        return restaurants, reviews, photos
        
    finally:
        conn.close()


def get_photo_url(photo_reference, max_width=400):
    """Convert photo_reference to Google Places API photo URL"""
    if pd.isna(photo_reference) or not photo_reference:
        return None
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={max_width}&photo_reference={photo_reference}&key={GOOGLE_PLACES_API_KEY}"


def preprocess_text(text):
    """Clean and preprocess review text for NLP"""
    if pd.isna(text):
        return ""
    text = str(text).lower().strip()
    text = text.replace(',', ' ')
    text = ' '.join(text.split())
    return text


# ============================================================================
# SMART SCORE CALCULATION
# ============================================================================

def calculate_review_quality_score(review):
    """
    Calculate individual review quality/authenticity score
    Based on: profile photo, Google profile, review length, recency
    """
    score = 0.0
    
    # Has profile photo (verified user)
    if pd.notna(review['profile_photo_url']) and review['profile_photo_url']:
        score += 0.25
    
    # Has Google profile URL (active reviewer)
    if pd.notna(review['author_url']) and 'contrib' in str(review['author_url']):
        score += 0.25
    
    # Review detail score (length indicates effort)
    text_length = len(review['text']) if pd.notna(review['text']) else 0
    if text_length > 200:
        score += 0.3
    elif text_length > 100:
        score += 0.15
    elif text_length > 50:
        score += 0.05
    
    # Recency bonus (recent reviews more relevant)
    days_ago = (datetime.now() - review['time']).days
    if days_ago < 30:
        score += 0.2
    elif days_ago < 90:
        score += 0.1
    elif days_ago < 180:
        score += 0.05
    
    return min(score, 1.0)


def calculate_momentum_score(restaurant_id, reviews_df):
    """
    Calculate restaurant momentum (trending vs declining)
    Based on: review velocity, rating trend
    """
    reviews = reviews_df[reviews_df['restaurant_id'] == restaurant_id].copy()
    
    if len(reviews) < 10:
        return 0.5  # Neutral for new restaurants
    
    reviews = reviews.sort_values('time')
    
    # Calculate review velocity (last 90 days vs previous 90 days)
    cutoff_date = datetime.now() - pd.Timedelta(days=90)
    recent_reviews = reviews[reviews['time'] >= cutoff_date]
    
    if len(recent_reviews) == 0:
        return 0.3  # Declining (no recent reviews)
    
    # Compare recent vs historical review rate
    recent_rate = len(recent_reviews) / 90  # Reviews per day
    historical_reviews = reviews[reviews['time'] < cutoff_date]
    
    if len(historical_reviews) > 0:
        days_historical = (cutoff_date - historical_reviews['time'].min()).days
        historical_rate = len(historical_reviews) / max(days_historical, 1)
        
        if historical_rate > 0:
            velocity_ratio = recent_rate / historical_rate
            velocity_score = min(velocity_ratio / 2, 1.0)  # Normalize
        else:
            velocity_score = 1.0  # New restaurant with reviews
    else:
        velocity_score = 1.0  # New restaurant
    
    # Rating trend (last 30 reviews vs previous)
    if len(reviews) >= 60:
        recent_rating = reviews.tail(30)['rating'].mean()
        previous_rating = reviews.iloc[-60:-30]['rating'].mean()
        rating_improvement = (recent_rating - previous_rating) + 0.5  # Normalize to 0-1
        rating_trend = max(0, min(rating_improvement, 1.0))
    else:
        rating_trend = 0.5  # Neutral
    
    # Combine (70% velocity, 30% rating trend)
    momentum = velocity_score * 0.7 + rating_trend * 0.3
    
    return momentum


def calculate_smart_score(restaurant, reviews_df, photos_df, similarity_score=0.0):
    """
    🎯 SMART SCORE: Multi-factor restaurant ranking
    
    Combines:
    1. Base Quality (30%): Rating & review count
    2. Review Authenticity (15%): Quality of reviews
    3. Momentum (10%): Trending vs declining
    4. Information Completeness (10%): Photos, website, hours
    5. Value (10%): Price-quality ratio
    6. Search Relevance (25%): Semantic similarity to query
    
    Returns: Score from 0-100
    """
    
    # 1. BASE QUALITY SCORE (30%)
    # Rating component (0-5 → 0-1)
    rating_normalized = restaurant['rating'] / 5.0 if pd.notna(restaurant['rating']) else 0
    
    # Review count component (log scale, cap at 1000)
    review_count = restaurant['user_ratings_total'] if pd.notna(restaurant['user_ratings_total']) else 0
    review_count_normalized = min(np.log1p(review_count) / np.log1p(1000), 1.0)
    
    # Social proof: more reviews = more confidence
    base_quality = (rating_normalized * 0.7 + review_count_normalized * 0.3)
    
    
    # 2. REVIEW AUTHENTICITY SCORE (15%)
    restaurant_reviews = reviews_df[reviews_df['restaurant_id'] == restaurant['id']]
    
    if len(restaurant_reviews) > 0:
        restaurant_reviews['quality_score'] = restaurant_reviews.apply(
            calculate_review_quality_score, axis=1
        )
        authenticity_score = restaurant_reviews['quality_score'].mean()
    else:
        authenticity_score = 0.5  # Neutral for no reviews
    
    
    # 3. MOMENTUM SCORE (10%)
    momentum = calculate_momentum_score(restaurant['id'], reviews_df)
    
    
    # 4. INFORMATION COMPLETENESS (10%)
    completeness = 0.0
    
    # Has photos
    restaurant_photos = photos_df[photos_df['restaurant_id'] == restaurant['id']]
    if len(restaurant_photos) > 0:
        completeness += 0.3
    
    # Has website
    if pd.notna(restaurant['website']) and restaurant['website']:
        completeness += 0.25
    
    # Has phone
    if pd.notna(restaurant['formatted_phone_number']) and restaurant['formatted_phone_number']:
        completeness += 0.15
    
    # Has hours
    if pd.notna(restaurant['open_times']) and restaurant['open_times']:
        completeness += 0.15
    
    # Has detailed amenities
    amenity_cols = ['serves_vegetarian', 'dine_in', 'takeout', 'delivery']
    amenity_count = sum([restaurant[col] for col in amenity_cols if col in restaurant.index])
    completeness += (amenity_count / len(amenity_cols)) * 0.15
    
    
    # 5. VALUE SCORE (10%)
    # Price-quality ratio (lower price + high rating = good value)
    if pd.notna(restaurant['price_level']) and restaurant['price_level'] > 0:
        # Normalize price (1-4 → 1.0-0.25)
        price_factor = 1.0 - ((restaurant['price_level'] - 1) / 3) * 0.75
        value_score = rating_normalized * price_factor
    else:
        value_score = rating_normalized  # Assume mid-price if unknown
    
    
    # 6. SEARCH RELEVANCE (25%)
    # Use similarity score from TF-IDF or BERT
    relevance = similarity_score
    
    
    # COMBINE ALL FACTORS
    smart_score = (
        base_quality * 0.30 +
        authenticity_score * 0.15 +
        momentum * 0.10 +
        completeness * 0.10 +
        value_score * 0.10 +
        relevance * 0.25
    )
    
    # Convert to 0-100 scale
    return smart_score * 100


def get_smart_score_breakdown(restaurant, reviews_df, photos_df, similarity_score=0.0):
    """Return detailed breakdown of smart score components"""
    
    # Calculate each component
    rating_normalized = restaurant['rating'] / 5.0 if pd.notna(restaurant['rating']) else 0
    review_count = restaurant['user_ratings_total'] if pd.notna(restaurant['user_ratings_total']) else 0
    review_count_normalized = min(np.log1p(review_count) / np.log1p(1000), 1.0)
    base_quality = (rating_normalized * 0.7 + review_count_normalized * 0.3) * 100
    
    restaurant_reviews = reviews_df[reviews_df['restaurant_id'] == restaurant['id']]
    if len(restaurant_reviews) > 0:
        restaurant_reviews['quality_score'] = restaurant_reviews.apply(calculate_review_quality_score, axis=1)
        authenticity = restaurant_reviews['quality_score'].mean() * 100
    else:
        authenticity = 50
    
    momentum = calculate_momentum_score(restaurant['id'], reviews_df) * 100
    
    # Completeness
    restaurant_photos = photos_df[photos_df['restaurant_id'] == restaurant['id']]
    completeness = 0.0
    if len(restaurant_photos) > 0:
        completeness += 0.3
    if pd.notna(restaurant['website']) and restaurant['website']:
        completeness += 0.25
    if pd.notna(restaurant['formatted_phone_number']):
        completeness += 0.15
    if pd.notna(restaurant['open_times']):
        completeness += 0.15
    amenity_cols = ['serves_vegetarian', 'dine_in', 'takeout', 'delivery']
    amenity_count = sum([restaurant[col] for col in amenity_cols if col in restaurant.index])
    completeness += (amenity_count / len(amenity_cols)) * 0.15
    completeness *= 100
    
    # Value
    if pd.notna(restaurant['price_level']) and restaurant['price_level'] > 0:
        price_factor = 1.0 - ((restaurant['price_level'] - 1) / 3) * 0.75
        value = rating_normalized * price_factor * 100
    else:
        value = rating_normalized * 100
    
    relevance = similarity_score * 100
    
    return {
        'Quality': base_quality,
        'Authenticity': authenticity,
        'Momentum': momentum,
        'Completeness': completeness,
        'Value': value,
        'Relevance': relevance
    }


# ============================================================================
# NLP FUNCTIONS (TF-IDF, BERT, Sentiment, Topics)
# ============================================================================

def calculate_tfidf_scores(restaurants, reviews, query):
    """TF-IDF vectorization for search relevance"""
    try:
        restaurants_sample = restaurants
        reviews_sample = reviews
        
        # Aggregate reviews per restaurant
        review_texts = reviews_sample.groupby('restaurant_id')['text'].apply(
            lambda x: ' '.join(x)
        ).reset_index()
        
        restaurants_with_reviews = restaurants_sample.merge(
            review_texts, 
            left_on='id', 
            right_on='restaurant_id', 
            how='left'
        )
        
        restaurants_with_reviews['combined_text'] = (
            restaurants_with_reviews['name'] + ' ' + 
            restaurants_with_reviews['cuisine'].fillna('') + ' ' + 
            restaurants_with_reviews['text'].fillna('')
        ).apply(preprocess_text)
        
        vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.98,
            lowercase=True,
            strip_accents='unicode'
        )
        
        tfidf_matrix = vectorizer.fit_transform(restaurants_with_reviews['combined_text'])
        processed_query = preprocess_text(query)
        query_vec = vectorizer.transform([processed_query])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        
        restaurants_with_reviews['similarity_score'] = similarities
        
        # Fallback to name matching if no TF-IDF matches
        if similarities.max() == 0:
            query_lower = query.lower()
            name_similarities = []
            for _, row in restaurants_with_reviews.iterrows():
                name = str(row['name']).lower()
                cuisine = str(row['cuisine']).lower() if pd.notna(row['cuisine']) else ''
                
                name_score = 0
                if query_lower in name:
                    name_score += 0.5
                if query_lower in cuisine:
                    name_score += 0.3
                
                query_words = query_lower.split()
                for word in query_words:
                    if word in name:
                        name_score += 0.2
                    if word in cuisine:
                        name_score += 0.1
                
                name_similarities.append(name_score)
            
            restaurants_with_reviews['similarity_score'] = name_similarities
        
        return restaurants_with_reviews.sort_values('similarity_score', ascending=False)
        
    except Exception as e:
        print(f"TF-IDF calculation failed: {e}")
        restaurants['similarity_score'] = 0.0
        return restaurants


def analyze_sentiment(reviews):
    """BERT-based sentiment analysis"""
    try:
        sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            return_all_scores=True
        )
        
        sample_reviews = reviews['text'].dropna().head(500)
        sentiments = []
        
        for text in sample_reviews:
            if len(text.strip()) > 0:
                try:
                    result = sentiment_pipeline(text[:512])
                    best_sentiment = max(result[0], key=lambda x: x['score'])
                    label = best_sentiment['label']
                    
                    if 'POSITIVE' in label.upper() or 'POS' in label.upper():
                        sentiments.append('Positive')
                    elif 'NEGATIVE' in label.upper() or 'NEG' in label.upper():
                        sentiments.append('Negative')
                    else:
                        sentiments.append('Neutral')
                except:
                    sentiments.append('Neutral')
            else:
                sentiments.append('Neutral')
        
        if sentiments:
            sentiment_counts = pd.Series(sentiments).value_counts()
            sentiment_pct = (sentiment_counts / len(sentiments) * 100).round(1)
        else:
            sentiment_pct = pd.Series({'Positive': 0, 'Neutral': 0, 'Negative': 0})
        
        return {
            'Positive': sentiment_pct.get('Positive', 0),
            'Neutral': sentiment_pct.get('Neutral', 0),
            'Negative': sentiment_pct.get('Negative', 0)
        }
        
    except Exception as e:
        print(f"Sentiment analysis failed: {e}")
        def get_sentiment(rating):
            if rating >= 4:
                return 'Positive'
            elif rating >= 3:
                return 'Neutral'
            else:
                return 'Negative'
        
        reviews['sentiment'] = reviews['rating'].apply(get_sentiment)
        sentiment_counts = reviews['sentiment'].value_counts()
        sentiment_pct = (sentiment_counts / len(reviews) * 100).round(1)
        
        return {
            'Positive': sentiment_pct.get('Positive', 0),
            'Neutral': sentiment_pct.get('Neutral', 0),
            'Negative': sentiment_pct.get('Negative', 0)
        }


def extract_topics(reviews, n_topics=5):
    """LDA topic modeling"""
    try:
        texts = reviews['text'].dropna().apply(preprocess_text)
        texts = texts[texts.str.len() > 10]
        
        if len(texts) < 10:
            return ['food', 'service', 'atmosphere', 'price', 'location']
        
        vectorizer = CountVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.8
        )
        
        doc_term_matrix = vectorizer.fit_transform(texts)
        
        lda_model = LatentDirichletAllocation(
            n_components=n_topics,
            random_state=42,
            max_iter=10,
            learning_method='online'
        )
        
        lda_model.fit(doc_term_matrix)
        feature_names = vectorizer.get_feature_names_out()
        topics = []
        
        for topic_idx, topic in enumerate(lda_model.components_):
            top_words_idx = topic.argsort()[-5:][::-1]
            top_words = [feature_names[i] for i in top_words_idx]
            topics.extend(top_words)
        
        seen = set()
        unique_topics = []
        for topic in topics:
            if topic not in seen:
                seen.add(topic)
                unique_topics.append(topic)
        
        return unique_topics[:n_topics] if unique_topics else ['food', 'service', 'atmosphere', 'price', 'location']
        
    except Exception as e:
        print(f"Topic modeling failed: {e}")
        return ['food', 'service', 'atmosphere', 'price', 'location']


# ============================================================================
# SHINY UI
# ============================================================================

app_ui = ui.page_fluid(
    ui.tags.style("""
        .landing-page {
            text-align: center;
            padding: 100px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }
        .hero-title {
            font-size: 4rem;
            font-weight: 800;
            margin-bottom: 1rem;
        }
        .search-container {
            max-width: 700px;
            margin: 2rem auto;
        }
        .filter-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .analytics-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .concept-badge {
            display: inline-block;
            padding: 4px 10px;
            background: #fef5e7;
            color: #d97706;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-left: 8px;
        }
        .restaurant-card {
            padding: 15px;
            background: #f7fafc;
            border-radius: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }
        .restaurant-card:hover {
            background: #edf2f7;
            transform: translateY(-2px);
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        }
        .photo-gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 8px;
            margin-top: 10px;
        }
        .photo-thumbnail {
            width: 100%;
            height: 100px;
            object-fit: cover;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .photo-thumbnail:hover {
            transform: scale(1.05);
        }
        .smart-score-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 1rem;
            margin-left: 10px;
        }
        .score-excellent { background: linear-gradient(135deg, #10b981, #059669); color: white; }
        .score-good { background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; }
        .score-average { background: linear-gradient(135deg, #f59e0b, #d97706); color: white; }
        .score-poor { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; }
        
        .photo-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        .photo-modal.active {
            display: flex;
        }
        .photo-modal img {
            max-width: 90%;
            max-height: 90%;
            border-radius: 8px;
        }
        .photo-modal-close {
            position: absolute;
            top: 20px;
            right: 30px;
            color: white;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
        }
    """),
    
    ui.tags.script("""
        function openPhotoModal(src) {
            const modal = document.getElementById('photoModal');
            const modalImg = document.getElementById('modalImage');
            modal.classList.add('active');
            modalImg.src = src;
        }
        
        function closePhotoModal() {
            document.getElementById('photoModal').classList.remove('active');
        }
    """),
    
    # Photo Modal
    ui.tags.div(
        {"id": "photoModal", "class": "photo-modal", "onclick": "closePhotoModal()"},
        ui.tags.span("×", {"class": "photo-modal-close"}),
        ui.tags.img(id="modalImage", src="")
    ),
    
    ui.navset_tab(
        # ====================================================================
        # TAB 1: LANDING PAGE
        # ====================================================================
        ui.nav_panel(
            "🏠 Home",
            ui.div(
                {"class": "landing-page"},
                ui.h1("🍽️ RestaurantAI", {"class": "hero-title"}),
                ui.p("Find your perfect dining experience using Smart Score™ + ML-powered search", 
                     style="font-size: 1.5rem; margin-bottom: 3rem;"),
                
                ui.div(
                    {"class": "search-container"},
                    ui.input_text(
                        "main_search",
                        None,
                        placeholder="Try: 'romantic Italian with outdoor seating' or 'spicy vegan brunch'...",
                        width="100%"
                    ),
                    ui.input_action_button(
                        "search_btn",
                        "🔍 Search Restaurants",
                        class_="btn-lg btn-primary",
                        style="margin-top: 1rem; padding: 15px 30px; font-size: 1.2rem;"
                    )
                ),
                
                ui.div(
                    {"style": "margin-top: 4rem;"},
                    ui.h3("Powered by Smart Score™ Algorithm"),
                    ui.p("Multi-factor ranking: Quality • Authenticity • Momentum • Completeness • Value • Relevance",
                         style="font-size: 1.1rem; margin-top: 1rem; opacity: 0.9;"),
                    ui.row(
                        ui.column(3, ui.div("🎯 Smart Scoring", style="font-weight: 600; margin-top: 2rem;")),
                        ui.column(3, ui.div("📸 Photo Gallery", style="font-weight: 600; margin-top: 2rem;")),
                        ui.column(3, ui.div("😊 Sentiment Analysis", style="font-weight: 600; margin-top: 2rem;")),
                        ui.column(3, ui.div("🔥 Momentum Tracking", style="font-weight: 600; margin-top: 2rem;")),
                    )
                )
            )
        ),
        
        # ====================================================================
        # TAB 2: SEARCH RESULTS
        # ====================================================================
        ui.nav_panel(
            "🔍 Search Results",
            
            ui.row(
                # LEFT COLUMN - FILTERS
                ui.column(
                    3,
                    ui.div(
                        {"class": "filter-card"},
                        ui.h4("🎛️ Filters"),
                        
                        ui.input_text("query_input", "Search Query", 
                                     placeholder="e.g., romantic Italian"),
                        
                        ui.input_selectize(
                            "cuisine_filter",
                            "Restaurant Type",
                            choices=["All", "restaurant", "bar", "cafe", "meal_takeaway", "meal_delivery"],
                            multiple=True
                        ),
                        
                        ui.input_slider(
                            "smart_score_filter",
                            "Minimum Smart Score",
                            min=0, max=100, value=60, step=5
                        ),
                        
                        ui.input_slider(
                            "rating_filter",
                            "Minimum Rating",
                            min=0, max=5, value=3.5, step=0.5
                        ),
                        
                        ui.input_checkbox("vegetarian_filter", "Vegetarian Options"),
                        ui.input_checkbox("has_photos_filter", "Has Photos"),
                        ui.input_checkbox("takeout_filter", "Takeout Available"),
                    )
                ),
                
                # CENTER COLUMN - RESULTS
                ui.column(
                    6,
                    ui.div(
                        {"style": "background: white; border-radius: 15px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);"},
                        
                        ui.h4("🏆 Top Matches (Smart Score™ Ranked)"),
                        ui.output_ui("restaurant_list")
                    )
                ),
                
                # RIGHT COLUMN - ANALYTICS
                ui.column(
                    3,
                    # Smart Score Breakdown
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h5([
                            "🎯 Smart Score",
                            ui.span("Multi-Factor", {"class": "concept-badge"})
                        ]),
                        ui.output_ui("smart_score_breakdown")
                    ),
                    
                    # Topic Keywords
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h5([
                            "🏷️ Key Topics",
                            ui.span("LDA", {"class": "concept-badge"})
                        ]),
                        ui.output_ui("topic_keywords")
                    ),
                    
                    # Sentiment Analysis
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h5([
                            "😊 Sentiment",
                            ui.span("BERT", {"class": "concept-badge"})
                        ]),
                        ui.output_ui("sentiment_plot")
                    ),
                )
            )
        ),
        
        # ====================================================================
        # TAB 3: ANALYTICS
        # ====================================================================
        ui.nav_panel(
            "📊 Analytics",
            ui.row(
                ui.column(
                    6,
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h4("Smart Score Distribution"),
                        ui.output_ui("smart_score_distribution")
                    )
                ),
                ui.column(
                    6,
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h4("Rating vs Smart Score"),
                        ui.output_ui("rating_vs_smart_score")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h4("Top Restaurants by Smart Score"),
                        ui.output_ui("top_restaurants_table")
                    )
                )
            )
        )
    ),
    id="main_tabs"
)


# ============================================================================
# SHINY SERVER
# ============================================================================

def server(input, output, session):
    
    # Load data
    restaurants_df, reviews_df, photos_df = load_data()
    
    # Calculate smart scores for all restaurants (do once at startup)
    @reactive.Calc
    def restaurants_with_smart_scores():
        """Calculate smart scores for all restaurants"""
        df = restaurants_df.copy()
        
        smart_scores = []
        for _, restaurant in df.iterrows():
            score = calculate_smart_score(
                restaurant, 
                reviews_df, 
                photos_df, 
                similarity_score=0.0  # No query context yet
            )
            smart_scores.append(score)
        
        df['smart_score'] = smart_scores
        return df
    
    # Navigation
    @reactive.Effect
    @reactive.event(input.search_btn)
    def navigate_to_search():
        ui.update_navset("main_tabs", selected="Search Results")
        if input.main_search():
            ui.update_text("query_input", value=input.main_search())
    
    # Filtered restaurants
    @reactive.Calc
    def filtered_restaurants():
        query = input.query_input() or input.main_search() or ""
        
        df = restaurants_with_smart_scores()
        
        if query:
            # Apply TF-IDF search
            filtered = calculate_tfidf_scores(df, reviews_df, query)
            
            # Recalculate smart scores with search relevance
            smart_scores = []
            for _, restaurant in filtered.iterrows():
                score = calculate_smart_score(
                    restaurant,
                    reviews_df,
                    photos_df,
                    similarity_score=restaurant['similarity_score']
                )
                smart_scores.append(score)
            
            filtered['smart_score'] = smart_scores
        else:
            filtered = df.copy()
        
        # Apply filters
        if input.rating_filter():
            filtered = filtered[filtered['rating'] >= input.rating_filter()]
        
        if input.smart_score_filter():
            filtered = filtered[filtered['smart_score'] >= input.smart_score_filter()]
        
        if input.cuisine_filter() and "All" not in input.cuisine_filter():
            cuisine_mask = filtered['cuisine'].str.contains('|'.join(input.cuisine_filter()), case=False, na=False)
            filtered = filtered[cuisine_mask]
        
        if input.vegetarian_filter():
            filtered = filtered[filtered['serves_vegetarian'] == True]
        
        if input.has_photos_filter():
            restaurant_ids_with_photos = photos_df['restaurant_id'].unique()
            filtered = filtered[filtered['id'].isin(restaurant_ids_with_photos)]
        
        if input.takeout_filter():
            filtered = filtered[filtered['takeout'] == True]
        
        return filtered.sort_values('smart_score', ascending=False).head(20)
    
    
    # Restaurant list with photos
    @output
    @render.ui
    def restaurant_list():
        df = filtered_restaurants()
        
        if len(df) == 0:
            return ui.p("No restaurants found matching your criteria.")
        
        cards = []
        for idx, row in df.head(10).iterrows():
            # Get photos for this restaurant
            restaurant_photos = photos_df[photos_df['restaurant_id'] == row['id']].head(4)
            
            # Smart score badge
            score = row['smart_score']
            if score >= 80:
                badge_class = "score-excellent"
                badge_text = f"🏆 {score:.0f}"
            elif score >= 70:
                badge_class = "score-good"
                badge_text = f"⭐ {score:.0f}"
            elif score >= 60:
                badge_class = "score-average"
                badge_text = f"👍 {score:.0f}"
            else:
                badge_class = "score-poor"
                badge_text = f"📊 {score:.0f}"
            
            # Photo gallery
            photo_gallery = ui.div()
            if len(restaurant_photos) > 0:
                photo_elements = []
                for _, photo in restaurant_photos.iterrows():
                    photo_url = get_photo_url(photo['photo_reference'], max_width=200)
                    if photo_url:
                        photo_elements.append(
                            ui.tags.img(
                                src=photo_url,
                                class_="photo-thumbnail",
                                onclick=f"openPhotoModal('{get_photo_url(photo['photo_reference'], max_width=800)}')"
                            )
                        )
                
                if photo_elements:
                    photo_gallery = ui.div(
                        {"class": "photo-gallery"},
                        *photo_elements
                    )
            
            # Create card
            card = ui.div(
                {"class": "restaurant-card"},
                ui.div(
                    ui.strong(row['name']),
                    ui.span(f" ⭐ {row['rating']}", style="color: #f59e0b; margin-left: 10px;"),
                    ui.span(badge_text, {"class": f"smart-score-badge {badge_class}"}),
                ),
                ui.div(
                    row['cuisine'],
                    style="color: #718096; font-size: 0.9rem; margin-top: 4px;"
                ),
                ui.div(
                    row['address'],
                    style="color: #a0aec0; font-size: 0.85rem; margin-top: 2px;"
                ),
                photo_gallery
            )
            cards.append(card)
        
        return ui.div(*cards)
    
    
    # Smart Score Breakdown
    @output
    @render.ui
    def smart_score_breakdown():
        df = filtered_restaurants()
        
        if len(df) == 0:
            return ui.p("Enter a search query to see score breakdown")
        
        top_match = df.iloc[0]
        query = input.query_input() or input.main_search() or ""
        similarity_score = top_match.get('similarity_score', 0.0) if query else 0.0
        
        breakdown = get_smart_score_breakdown(
            top_match,
            reviews_df,
            photos_df,
            similarity_score
        )
        
        bars = []
        colors = {
            'Quality': '#10b981',
            'Authenticity': '#3b82f6',
            'Momentum': '#f59e0b',
            'Completeness': '#8b5cf6',
            'Value': '#ec4899',
            'Relevance': '#667eea'
        }
        
        for component, score in breakdown.items():
            bar = ui.div(
                ui.div(component, style="width: 100px; font-size: 0.85rem; font-weight: 600;"),
                ui.div(
                    {"style": "flex: 1; height: 24px; background: #e0e6ed; border-radius: 12px; overflow: hidden;"},
                    ui.div(
                        style=f"width: {score}%; height: 100%; background: {colors[component]}; border-radius: 12px; transition: width 0.3s;"
                    )
                ),
                ui.div(f"{score:.0f}", style="width: 35px; text-align: right; font-weight: 600; font-size: 0.85rem;"),
                style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;"
            )
            bars.append(bar)
        
        total_score = top_match['smart_score']
        
        return ui.div(
            ui.div(f"Restaurant: {top_match['name']}", style="font-weight: 600; margin-bottom: 15px; font-size: 0.9rem;"),
            *bars,
            ui.hr(),
            ui.div(
                f"Smart Score: {total_score:.0f}/100",
                style="font-size: 1.2rem; font-weight: 700; color: #667eea; text-align: center; margin-top: 10px;"
            )
        )
    
    
    # Topic Keywords
    @output
    @render.ui
    def topic_keywords():
        topics = extract_topics(reviews_df)
        
        keywords = [
            ui.span(
                topic.title(),
                style="display: inline-block; padding: 6px 12px; margin: 4px; "
                      "background: rgba(102, 126, 234, 0.1); border: 1px solid rgba(102, 126, 234, 0.3); "
                      "border-radius: 15px; font-size: 0.85rem;"
            )
            for topic in topics
        ]
        
        return ui.div(*keywords)
    
    
    # Sentiment Plot
    @output
    @render.ui
    def sentiment_plot():
        sentiment_data = analyze_sentiment(reviews_df)
        
        bars = []
        colors = {
            'Positive': '#48bb78',
            'Neutral': '#ecc94b',
            'Negative': '#f56565'
        }
        
        for sentiment, pct in sentiment_data.items():
            bar = ui.div(
                ui.div(sentiment, style="width: 80px; font-size: 0.85rem;"),
                ui.div(
                    {"style": "flex: 1; height: 20px; background: #e0e6ed; border-radius: 10px; overflow: hidden;"},
                    ui.div(
                        style=f"width: {pct}%; height: 100%; background: {colors[sentiment]}; border-radius: 10px;"
                    )
                ),
                ui.div(f"{pct}%", style="width: 40px; text-align: right; font-weight: 600; font-size: 0.85rem;"),
                style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;"
            )
            bars.append(bar)
        
        return ui.div(*bars)
    
    
    # Smart Score Distribution
    @output
    @render.ui
    def smart_score_distribution():
        df = restaurants_with_smart_scores()
        
        fig = px.histogram(
            df,
            x='smart_score',
            nbins=20,
            title='Distribution of Smart Scores',
            labels={'smart_score': 'Smart Score', 'count': 'Number of Restaurants'},
            color_discrete_sequence=['#667eea']
        )
        fig.update_layout(height=300)
        return ui.HTML(fig.to_html(include_plotlyjs='cdn'))
    
    
    # Rating vs Smart Score
    @output
    @render.ui
    def rating_vs_smart_score():
        df = restaurants_with_smart_scores()
        
        fig = px.scatter(
            df,
            x='rating',
            y='smart_score',
            size='user_ratings_total',
            hover_name='name',
            title='Rating vs Smart Score',
            labels={'rating': 'Google Rating', 'smart_score': 'Smart Score'},
            color='smart_score',
            color_continuous_scale='Viridis'
        )
        fig.update_layout(height=350)
        return ui.HTML(fig.to_html(include_plotlyjs='cdn'))
    
    
    # Top Restaurants Table
    @output
    @render.ui
    def top_restaurants_table():
        df = restaurants_with_smart_scores()
        top_20 = df.nlargest(20, 'smart_score')
        
        rows = []
        for i, (idx, row) in enumerate(top_20.iterrows(), 1):
            # Get photo count
            photo_count = len(photos_df[photos_df['restaurant_id'] == row['id']])
            
            # Score badge
            score = row['smart_score']
            if score >= 80:
                badge = "🏆"
            elif score >= 70:
                badge = "⭐"
            else:
                badge = "📊"
            
            row_html = ui.tags.tr(
                ui.tags.td(str(i), style="font-weight: 600;"),
                ui.tags.td(badge + " " + row['name']),
                ui.tags.td(f"{score:.1f}", style="font-weight: 700; color: #667eea;"),
                ui.tags.td(f"⭐ {row['rating']:.1f}"),
                ui.tags.td(str(row['user_ratings_total'])),
                ui.tags.td(f"📸 {photo_count}"),
                ui.tags.td(row['cuisine'][:30] + "..." if len(str(row['cuisine'])) > 30 else row['cuisine'])
            )
            rows.append(row_html)
        
        return ui.tags.table(
            {"class": "table table-striped", "style": "width: 100%;"},
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("#"),
                    ui.tags.th("Restaurant"),
                    ui.tags.th("Smart Score"),
                    ui.tags.th("Rating"),
                    ui.tags.th("Reviews"),
                    ui.tags.th("Photos"),
                    ui.tags.th("Cuisine")
                )
            ),
            ui.tags.tbody(*rows)
        )


# ============================================================================
# CREATE APP
# ============================================================================

app = App(app_ui, server)
