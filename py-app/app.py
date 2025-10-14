"""
Restaurant Recommender - Shiny for Python Application
Implements: TF-IDF, BERT Embeddings, Sentiment Analysis, Topic Modeling, Cosine Similarity
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
from shiny.session import get_current_session
import torch
from transformers import pipeline, AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# DATA LOADING & PREPROCESSING
# ============================================================================

def load_data():
    """
    Load data from austin_restaurants.db SQLite database
    Returns:
        - restaurants: DataFrame with restaurant basic info + details
        - reviews: DataFrame with review text and ratings
    """
    # Get the path to the database (one level up from py-app folder)
    db_path = os.path.join(os.path.dirname(__file__), '..', 'austin_restaurants.db')
    
    # Connect to SQLite database
    conn = sqlite3.connect(db_path)
    
    try:
        # Load restaurants with place details (LEFT JOIN to keep all restaurants)
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
            pd.formatted_phone_number
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
            rating,
            text,
            time
        FROM reviews
        WHERE text IS NOT NULL AND text != ''
        """
        reviews = pd.read_sql_query(reviews_query, conn)
        
        # Convert Unix timestamp to datetime for reviews
        reviews['time'] = pd.to_datetime(reviews['time'], unit='s')
        
        # Convert boolean columns (SQLite stores as 0/1)
        bool_cols = ['serves_vegetarian', 'dine_in', 'takeout', 'delivery', 
                     'serves_beer', 'serves_wine', 'serves_breakfast', 
                     'serves_brunch', 'serves_lunch', 'serves_dinner']
        for col in bool_cols:
            if col in restaurants.columns:
                restaurants[col] = restaurants[col].astype(bool)
        
        # Add outdoor_seating column (not in DB, set to False for now)
        restaurants['outdoor_seating'] = False
        
        print(f"Loaded {len(restaurants)} restaurants and {len(reviews)} reviews from database")
        
        return restaurants, reviews
        
    finally:
        conn.close()


def preprocess_text(text):
    """Clean and preprocess review text for NLP"""
    if pd.isna(text):
        return ""
    
    # Convert to string and clean
    text = str(text).lower().strip()
    
    # Replace commas with spaces in place_tags (cuisine data)
    text = text.replace(',', ' ')
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text


def calculate_tfidf_scores(restaurants, reviews, query):
    """
    CONCEPT: TF-IDF Vectorization
    Convert text to numerical vectors and rank by relevance
    """
    try:
        # Use ALL available data - no sampling
        restaurants_sample = restaurants
        reviews_sample = reviews
    
    # Aggregate reviews per restaurant
    review_texts = reviews_sample.groupby('restaurant_id')['text'].apply(
        lambda x: ' '.join(x)
    ).reset_index()
    
    # Merge with restaurant info
    restaurants_with_reviews = restaurants_sample.merge(
        review_texts, 
        left_on='id', 
        right_on='restaurant_id', 
        how='left'
    )
    
    # Create combined text: name + cuisine + reviews
    restaurants_with_reviews['combined_text'] = (
        restaurants_with_reviews['name'] + ' ' + 
        restaurants_with_reviews['cuisine'].fillna('') + ' ' + 
        restaurants_with_reviews['text'].fillna('')
    ).apply(preprocess_text)
    
    # TF-IDF Vectorization with more lenient parameters
    vectorizer = TfidfVectorizer(
        max_features=1000,
        stop_words='english',
        ngram_range=(1, 2),
        min_df=1,  # Include terms that appear in at least 1 document
        max_df=0.98,  # More lenient - exclude terms in more than 98% of documents
        lowercase=True,
        strip_accents='unicode'
    )
    
    # Fit on restaurant texts
    tfidf_matrix = vectorizer.fit_transform(
        restaurants_with_reviews['combined_text']
    )
    
    # Transform query with preprocessing
    processed_query = preprocess_text(query)
    query_vec = vectorizer.transform([processed_query])
    
    # Calculate cosine similarity (CONCEPT: Cosine Similarity)
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    
    restaurants_with_reviews['similarity_score'] = similarities
    
    # If no matches found, try fuzzy matching with restaurant names
    if similarities.max() == 0:
        print(f"No TF-IDF matches found for query: '{query}'")
        # Add name-based similarity as fallback
        query_lower = query.lower()
        name_similarities = []
        for _, row in restaurants_with_reviews.iterrows():
            name = str(row['name']).lower()
            cuisine = str(row['cuisine']) if pd.notna(row['cuisine']) else ''
            cuisine = cuisine.lower()
            
            # Simple keyword matching
            name_score = 0
            if query_lower in name:
                name_score += 0.5
            if query_lower in cuisine:
                name_score += 0.3
            
            # Check for partial matches
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
        # Return restaurants with zero similarity scores as fallback
        restaurants['similarity_score'] = 0.0
        return restaurants.sort_values('rating', ascending=False)


def analyze_sentiment(reviews):
    """
    CONCEPT: BERT-based Sentiment Analysis
    Uses pre-trained BERT model for accurate sentiment classification
    """
    try:
        # Initialize BERT sentiment analysis pipeline
        sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            tokenizer="cardiffnlp/twitter-roberta-base-sentiment-latest",
            return_all_scores=True
        )
        
        # Use a reasonable sample for sentiment analysis (BERT is slower)
        # But still use more data than before for better accuracy
        sample_reviews = reviews['text'].dropna().head(500)
        
        # Get BERT sentiment predictions
        sentiments = []
        for text in sample_reviews:
            if len(text.strip()) > 0:
                try:
                    result = sentiment_pipeline(text[:512])  # Limit text length
                    # Get the highest scoring sentiment
                    best_sentiment = max(result[0], key=lambda x: x['score'])
                    label = best_sentiment['label']
                    
                    # Map BERT labels to our labels
                    if 'POSITIVE' in label.upper() or 'POS' in label.upper():
                        sentiments.append('Positive')
                    elif 'NEGATIVE' in label.upper() or 'NEG' in label.upper():
                        sentiments.append('Negative')
                    else:
                        sentiments.append('Neutral')
                except:
                    # Fallback to rating-based sentiment
                    sentiments.append('Neutral')
            else:
                sentiments.append('Neutral')
        
        # Calculate percentages
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
        print(f"BERT sentiment analysis failed: {e}")
        # Fallback to rating-based sentiment
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
    """
    CONCEPT: LDA Topic Modeling
    Uses Latent Dirichlet Allocation for proper topic discovery
    """
    try:
        # Preprocess review texts
        texts = reviews['text'].dropna().apply(preprocess_text)
        texts = texts[texts.str.len() > 10]  # Filter out very short texts
        
        if len(texts) < 10:  # Need minimum documents for LDA
            return ['food', 'service', 'atmosphere', 'price', 'location']
        
        # Create document-term matrix
        vectorizer = CountVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2,  # Term must appear in at least 2 documents
            max_df=0.8  # Term can't appear in more than 80% of documents
        )
        
        doc_term_matrix = vectorizer.fit_transform(texts)
        
        # Apply LDA
        lda_model = LatentDirichletAllocation(
            n_components=n_topics,
            random_state=42,
            max_iter=10,
            learning_method='online'
        )
        
        lda_model.fit(doc_term_matrix)
        
        # Extract top words for each topic
        feature_names = vectorizer.get_feature_names_out()
        topics = []
        
        for topic_idx, topic in enumerate(lda_model.components_):
            top_words_idx = topic.argsort()[-5:][::-1]  # Top 5 words
            top_words = [feature_names[i] for i in top_words_idx]
            topics.extend(top_words)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_topics = []
        for topic in topics:
            if topic not in seen:
                seen.add(topic)
                unique_topics.append(topic)
        
        return unique_topics[:n_topics] if unique_topics else ['food', 'service', 'atmosphere', 'price', 'location']
        
    except Exception as e:
        print(f"LDA topic modeling failed: {e}")
        # Fallback to simple keyword extraction
        vectorizer = CountVectorizer(
            max_features=n_topics,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        texts = reviews['text'].apply(preprocess_text)
        word_matrix = vectorizer.fit_transform(texts)
        
        topics = vectorizer.get_feature_names_out()
        return topics if len(topics) > 0 else ['food', 'service', 'atmosphere', 'price', 'location']


def calculate_bert_similarity(restaurants, reviews, query):
    """
    CONCEPT: BERT Embeddings for Semantic Similarity
    Uses sentence transformers for semantic understanding beyond keyword matching
    """
    try:
        # Initialize sentence transformer model
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Use ALL available data - no sampling
        restaurants_sample = restaurants
        reviews_sample = reviews
        
        # Aggregate reviews per restaurant
        review_texts = reviews_sample.groupby('restaurant_id')['text'].apply(
            lambda x: ' '.join(x)
        ).reset_index()
        
        # Merge with restaurant info
        restaurants_with_reviews = restaurants_sample.merge(
            review_texts, 
            left_on='id', 
            right_on='restaurant_id', 
            how='left'
        )
        
        # Create combined text: name + cuisine + reviews
        restaurants_with_reviews['combined_text'] = (
            restaurants_with_reviews['name'] + ' ' + 
            restaurants_with_reviews['cuisine'].fillna('') + ' ' + 
            restaurants_with_reviews['text'].fillna('')
        ).apply(preprocess_text)
        
        # Get BERT embeddings for restaurant texts
        restaurant_texts = restaurants_with_reviews['combined_text'].tolist()
        restaurant_embeddings = model.encode(restaurant_texts)
        
        # Get BERT embedding for query
        query_embedding = model.encode([preprocess_text(query)])
        
        # Calculate cosine similarity
        similarities = cosine_similarity(query_embedding, restaurant_embeddings).flatten()
        
        restaurants_with_reviews['bert_similarity_score'] = similarities
        
        return restaurants_with_reviews.sort_values('bert_similarity_score', ascending=False)
        
    except Exception as e:
        print(f"BERT similarity calculation failed: {e}")
        # Fallback to TF-IDF
        return calculate_tfidf_scores(restaurants, reviews, query)


# ============================================================================
# SHINY UI
# ============================================================================

app_ui = ui.page_fluid(
    # Custom CSS
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
        }
        .restaurant-card:hover {
            background: #edf2f7;
            transform: translateX(5px);
        }
        
        /* Clickable restaurant card styles */
        .clickable-restaurant {
            transition: all 0.2s ease;
            border: 2px solid transparent;
        }
        .clickable-restaurant:hover {
            background-color: #f7fafc !important;
            border-color: #667eea;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        }
        .clickable-restaurant:active {
            transform: translateY(0);
            box-shadow: 0 2px 6px rgba(102, 126, 234, 0.2);
        }
    """),
    
    # JavaScript for click handling
    ui.tags.script("""
        $(document).on('click', '.clickable-restaurant', function() {
            var restaurantId = $(this).data('restaurant-id');
            var lat = $(this).data('lat');
            var lng = $(this).data('lng');
            
            // Add visual feedback
            $(this).css('background-color', '#e2e8f0');
            setTimeout(function() {
                $(this).css('background-color', '');
            }.bind(this), 200);
            
            // For now, just show an alert - in a full implementation,
            // this would trigger a map popup or navigation
            alert('Clicked restaurant: ' + $(this).find('strong').text() + 
                  '\\nLocation: ' + lat + ', ' + lng);
        });
    """),
    
    # Navigation
    ui.navset_tab(
        # ====================================================================
        # TAB 1: LANDING PAGE
        # ====================================================================
        ui.nav_panel(
            "🏠 Home",
            ui.div(
                {"class": "landing-page"},
                ui.h1("🍽️ RestaurantAI", {"class": "hero-title"}),
                ui.p("Find your perfect dining experience using advanced ML-powered search", 
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
                    ui.h3("Powered by Advanced NLP & ML"),
                    ui.row(
                        ui.column(3, ui.div("🎯 BERT Embeddings", style="font-weight: 600;")),
                        ui.column(3, ui.div("📊 TF-IDF Ranking", style="font-weight: 600;")),
                        ui.column(3, ui.div("😊 Sentiment Analysis", style="font-weight: 600;")),
                        ui.column(3, ui.div("🏷️ Topic Modeling", style="font-weight: 600;")),
                    )
                )
            )
        ),
        
        # ====================================================================
        # TAB 2: SEARCH RESULTS (Three-Column Layout)
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
                        
                        ui.input_select(
                            "similarity_method",
                            "Similarity Method",
                            choices={
                                "tfidf": "TF-IDF (Fast)",
                                "bert": "BERT Embeddings (Semantic)"
                            },
                            selected="tfidf"
                        ),
                        
                        ui.input_selectize(
                            "cuisine_filter",
                            "Restaurant Type",
                            choices=["All", "restaurant", "bar", "cafe", "meal_takeaway", "meal_delivery"],
                            multiple=True
                        ),
                        
                        ui.input_slider(
                            "rating_filter",
                            "Minimum Rating",
                            min=0, max=5, value=3.5, step=0.5
                        ),
                        
                        ui.input_slider(
                            "distance_filter",
                            "Distance (miles)",
                            min=0, max=25, value=10
                        ),
                        
                        ui.input_checkbox("vegetarian_filter", "Vegetarian Options"),
                        ui.input_checkbox("outdoor_filter", "Outdoor Seating"),
                        ui.input_checkbox("takeout_filter", "Takeout Available"),
                    )
                ),
                
                # CENTER COLUMN - MAP & RESULTS
                ui.column(
                    6,
                    ui.div(
                        {"style": "background: white; border-radius: 15px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);"},
                        
                        ui.h4("📍 Restaurant Map"),
                        ui.output_ui("map_plot"),
                        
                        ui.hr(),
                        
                        ui.h4("Top Matches"),
                        ui.output_ui("restaurant_list")
                    )
                ),
                
                # RIGHT COLUMN - ANALYTICS
                ui.column(
                    3,
                    # TF-IDF Scores Card
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h5([
                            "🏆 Top Matches",
                            ui.span("TF-IDF", {"class": "concept-badge"})
                        ]),
                        ui.output_ui("tfidf_rankings")
                    ),
                    
                    # Topic Keywords Card
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h5([
                            "🏷️ Key Topics",
                            ui.span("LDA", {"class": "concept-badge"})
                        ]),
                        ui.output_ui("topic_keywords")
                    ),
                    
                    # Sentiment Analysis Card
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h5([
                            "😊 Sentiment",
                            ui.span("BERT", {"class": "concept-badge"})
                        ]),
                        ui.output_ui("sentiment_plot")
                    ),
                    
                    # Similarity Score Card
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h5([
                            "🎯 Match Score",
                            ui.span("Cosine Sim", {"class": "concept-badge"})
                        ]),
                        ui.output_ui("similarity_score")
                    )
                )
            )
        ),
        
        # ====================================================================
        # TAB 3: ANALYTICS DASHBOARD
        # ====================================================================
        ui.nav_panel(
            "📊 Analytics",
            ui.row(
                ui.column(
                    6,
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h4("Rating Distribution"),
                        ui.output_ui("rating_distribution")
                    )
                ),
                ui.column(
                    6,
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h4("Price Range Analysis"),
                        ui.output_ui("price_analysis")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.div(
                        {"class": "analytics-card"},
                        ui.h4("Review Sentiment Over Time"),
                        ui.output_ui("sentiment_timeline")
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
    restaurants_df, reviews_df = load_data()
    
    # Navigation: Handle landing page search button
    @reactive.Effect
    @reactive.event(input.search_btn)
    def navigate_to_search():
        navigate_to_search_results()
    
    # Also handle Enter key press in main search
    @reactive.Effect
    @reactive.event(input.main_search)
    def handle_enter_search():
        # This will trigger when user types in main_search
        pass
    
    def navigate_to_search_results():
        """Navigate to search results and populate query"""
        # Switch to Search Results tab
        ui.update_navset("main_tabs", selected="Search Results")
        
        # Copy main_search value to query_input
        if input.main_search():
            ui.update_text("query_input", value=input.main_search())
    
    # Reactive: Filtered restaurants based on search and filters
    @reactive.Calc
    def filtered_restaurants():
        query = input.query_input() or input.main_search() or ""
        
        if not query:
            filtered = restaurants_df.copy()
        else:
            # Apply similarity ranking based on selected method
            similarity_method = input.similarity_method()
            if similarity_method == "bert":
                filtered = calculate_bert_similarity(restaurants_df, reviews_df, query)
            else:
                filtered = calculate_tfidf_scores(restaurants_df, reviews_df, query)
        
        # Apply filters
        if input.rating_filter():
            filtered = filtered[filtered['rating'] >= input.rating_filter()]
        
        # Apply cuisine filter
        if input.cuisine_filter() and "All" not in input.cuisine_filter():
            cuisine_mask = filtered['cuisine'].str.contains('|'.join(input.cuisine_filter()), case=False, na=False)
            filtered = filtered[cuisine_mask]
        
        if input.vegetarian_filter():
            filtered = filtered[filtered['serves_vegetarian'] == True]
        
        if input.outdoor_filter():
            filtered = filtered[filtered['outdoor_seating'] == True]
        
        if input.takeout_filter():
            filtered = filtered[filtered['takeout'] == True]
        
        return filtered.head(20)  # Top 20 results
    
    
    # Map visualization
    @output
    @render.ui
    def map_plot():
        df = filtered_restaurants()
        
        if len(df) == 0:
            # Return empty map if no data
            fig = px.scatter_mapbox(
                lat=[30.2672], lon=[-97.7431],
                zoom=11, height=400
            )
            fig.update_layout(
                mapbox_style="open-street-map",
                margin={"r":0,"t":0,"l":0,"b":0}
            )
            return ui.HTML(fig.to_html(include_plotlyjs='cdn'))
        
        # Create rich hover text with restaurant details
        hover_texts = []
        for idx, row in df.iterrows():
            # Get sample reviews for this restaurant
            restaurant_reviews = reviews_df().query(f"restaurant_id == {row['id']}").nlargest(3, 'rating')
            
            # Create star rating display
            rating_val = row['rating'] if pd.notna(row['rating']) else 0
            stars = "⭐" * int(rating_val)
            half_star = "⭐" if rating_val % 1 >= 0.5 else ""
            star_display = f"{stars}{half_star} ({rating_val})"
            
            # Similarity score
            similarity_html = ""
            if 'bert_similarity_score' in row and pd.notna(row['bert_similarity_score']) and row['bert_similarity_score'] > 0:
                similarity_html = f"<br>🎯 Match Score: {row['bert_similarity_score']:.2f}"
            elif 'similarity_score' in row and pd.notna(row['similarity_score']) and row['similarity_score'] > 0:
                similarity_html = f"<br>🎯 Match Score: {row['similarity_score']:.2f}"
            
            # Price level
            price_display = ""
            if pd.notna(row['price_level']):
                price_symbols = "$" * int(row['price_level'])
                price_display = f"<br>💰 {price_symbols}"
            
            # Amenities
            amenities = []
            if pd.notna(row['serves_vegetarian']) and row['serves_vegetarian']:
                amenities.append("🌱 Vegetarian")
            if pd.notna(row['takeout']) and row['takeout']:
                amenities.append("📦 Takeout")
            if pd.notna(row['delivery']) and row['delivery']:
                amenities.append("🚚 Delivery")
            if pd.notna(row['serves_beer']) and row['serves_beer']:
                amenities.append("🍺 Beer")
            if pd.notna(row['serves_wine']) and row['serves_wine']:
                amenities.append("🍷 Wine")
            if pd.notna(row['outdoor_seating']) and row['outdoor_seating']:
                amenities.append("🌞 Outdoor")
            
            amenities_html = "<br>" + " • ".join(amenities) if amenities else ""
            
            # Reviews
            reviews_html = ""
            if len(restaurant_reviews) > 0:
                review_items = []
                for _, review in restaurant_reviews.head(2).iterrows():
                    review_stars = "⭐" * int(review['rating'])
                    review_text = review['text'][:100] + "..." if len(review['text']) > 100 else review['text']
                    review_items.append(f"<div style='margin: 4px 0; padding: 4px; background: #f7fafc; border-radius: 4px;'><div style='color: #f59e0b; font-size: 0.9em;'>{review_stars} {review['rating']}</div><div style='font-size: 0.85em; color: #4a5568;'>{review_text}</div></div>")
                
                reviews_html = "<br><div style='margin: 8px 0;'><div style='font-weight: bold; color: #2d3748; margin-bottom: 4px;'>Recent Reviews:</div>" + "".join(review_items) + "</div>"
            
            # Action buttons
            links_html = "<br><div style='margin: 8px 0;'>"
            if pd.notna(row['website']) and row['website']:
                links_html += f"<a href='{row['website']}' target='_blank' style='display: inline-block; margin: 2px; padding: 6px 12px; background: #667eea; color: white; text-decoration: none; border-radius: 4px; font-size: 0.85em;'>🌐 Website</a>"
            if pd.notna(row['formatted_phone_number']) and row['formatted_phone_number']:
                links_html += f"<a href='tel:{row['formatted_phone_number']}' style='display: inline-block; margin: 2px; padding: 6px 12px; background: #38a169; color: white; text-decoration: none; border-radius: 4px; font-size: 0.85em;'>📞 Call</a>"
            links_html += "</div>"
            
            # Combine all HTML
            hover_text = f"""
            <div style='max-width: 350px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;'>
                <div style='border-bottom: 2px solid #667eea; padding-bottom: 8px; margin-bottom: 12px;'>
                    <h3 style='margin: 0; color: #2d3748; font-size: 1.2em;'>{row['name']}</h3>
                    <div style='color: #f59e0b; font-size: 1.1em; margin: 4px 0;'>{star_display}</div>
                    <div style='color: #718096; font-size: 0.9em;'>{row['user_ratings_total']} reviews</div>
                </div>
                {similarity_html}
                <div style='margin: 8px 0;'>
                    <span style='background: #edf2f7; padding: 4px 8px; border-radius: 12px; font-size: 0.85em; color: #4a5568;'>{row['cuisine']}</span>
                    {price_display}
                </div>
                {amenities_html}
                <div style='margin: 8px 0; padding: 8px; background: #f7fafc; border-radius: 4px;'>
                    <div style='font-size: 0.9em; color: #4a5568;'>📍 {row['address']}</div>
                </div>
                {reviews_html}
                {links_html}
            </div>
            """
            hover_texts.append(hover_text)
        
        # Create color palette based on rating
        def get_marker_color(rating):
            if pd.isna(rating):
                return "#gray"
            if rating >= 4.5:
                return "#10b981"  # Green
            elif rating >= 4.0:
                return "#f59e0b"  # Orange
            elif rating >= 3.5:
                return "#ef4444"  # Red
            else:
                return "#6b7280"  # Gray
        
        # Create size based on review count
        def get_marker_size(review_count):
            if pd.isna(review_count):
                return 6
            size = np.sqrt(review_count) / 3
            return max(6, min(20, size))
        
        # Apply colors and sizes
        df['marker_color'] = df['rating'].apply(get_marker_color)
        df['marker_size'] = df['user_ratings_total'].apply(get_marker_size)
        
        fig = px.scatter_mapbox(
            df,
            lat='lat',
            lon='lng',
            hover_name='name',
            hover_data={'rating': True, 'cuisine': True, 'address': True},
            color='marker_color',
            size='marker_size',
            zoom=11,
            height=400,
            custom_data=['id', 'lat', 'lng']  # Add custom data for click handling
        )
        
        # Update hover template with rich content
        fig.update_traces(
            hovertemplate='%{hovertext}<extra></extra>',
            hovertext=hover_texts
        )
        
        fig.update_layout(
            mapbox_style="carto-positron",
            margin={"r":0,"t":0,"l":0,"b":0},
            showlegend=False
        )
        
        # Add legend
        fig.add_trace(go.Scattermapbox(
            lat=[None], lon=[None],
            mode='markers',
            marker=dict(size=10, color='#10b981'),
            name='4.5+ Stars',
            showlegend=True
        ))
        fig.add_trace(go.Scattermapbox(
            lat=[None], lon=[None],
            mode='markers',
            marker=dict(size=10, color='#f59e0b'),
            name='4.0-4.4 Stars',
            showlegend=True
        ))
        fig.add_trace(go.Scattermapbox(
            lat=[None], lon=[None],
            mode='markers',
            marker=dict(size=10, color='#ef4444'),
            name='3.5-3.9 Stars',
            showlegend=True
        ))
        fig.add_trace(go.Scattermapbox(
            lat=[None], lon=[None],
            mode='markers',
            marker=dict(size=10, color='#6b7280'),
            name='Below 3.5',
            showlegend=True
        ))
        
        return ui.HTML(fig.to_html(include_plotlyjs='cdn'))
    
    
    # Restaurant list
    @output
    @render.ui
    def restaurant_list():
        df = filtered_restaurants()
        
        if len(df) == 0:
            return ui.p("No restaurants found matching your criteria.")
        
        cards = []
        for idx, row in df.head(10).iterrows():
            # Check which similarity score is available
            if 'bert_similarity_score' in row:
                score = row['bert_similarity_score']
            elif 'similarity_score' in row:
                score = row['similarity_score']
            else:
                score = 0
            
            # Create clickable card with data attributes
            card = ui.div(
                {
                    "class": "restaurant-card clickable-restaurant",
                    "data-restaurant-id": str(row['id']),
                    "data-lat": str(row['lat']),
                    "data-lng": str(row['lng']),
                    "style": "cursor: pointer; transition: all 0.2s ease; border: 2px solid transparent;"
                },
                ui.div(
                    ui.strong(row['name']),
                    ui.span(f" ⭐ {row['rating']}", style="color: #f59e0b; margin-left: 10px;"),
                    ui.span(f" 🎯 {score:.2f}", style="color: #667eea; margin-left: 10px;") if score > 0 else "",
                ),
                ui.div(
                    row['cuisine'],
                    style="color: #718096; font-size: 0.9rem;"
                ),
                ui.div(
                    row['address'],
                    style="color: #a0aec0; font-size: 0.85rem;"
                )
            )
            cards.append(card)
        
        return ui.div(*cards)
    
    
    # TF-IDF Rankings
    @output
    @render.ui
    def tfidf_rankings():
        df = filtered_restaurants()
        
        # Check which similarity score is available
        if 'bert_similarity_score' in df.columns:
            top_3 = df.nlargest(3, 'bert_similarity_score')
            score_col = 'bert_similarity_score'
            method = "BERT"
        elif 'similarity_score' in df.columns:
            top_3 = df.nlargest(3, 'similarity_score')
            score_col = 'similarity_score'
            method = "TF-IDF"
        else:
            return ui.p("Enter a search query to see rankings")
        
        items = []
        for i, (idx, row) in enumerate(top_3.iterrows(), 1):
            items.append(
                ui.div(
                    ui.span(f"{i}.", style="font-weight: 700; margin-right: 10px;"),
                    ui.span(row['name'], style="font-weight: 600;"),
                    ui.span(f"{row[score_col]:.3f}", 
                           style="float: right; color: #047857; font-weight: 600;")
                )
            )
        
        return ui.div(
            ui.div(f"Method: {method}", style="color: #667eea; font-size: 0.75rem; margin-bottom: 10px;"),
            *items
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
    
    
    # Similarity Score
    @output
    @render.ui
    def similarity_score():
        df = filtered_restaurants()
        query = input.query_input() or input.main_search() or ""
        
        if query and len(df) > 0:
            top_match = df.iloc[0]
            
            # Check which similarity score is available
            if 'bert_similarity_score' in df.columns:
                score = top_match['bert_similarity_score']
                method = "BERT"
            elif 'similarity_score' in df.columns:
                score = top_match['similarity_score']
                method = "TF-IDF"
            else:
                return ui.p("Enter a search query to see match scores")
            
            return ui.div(
                ui.div(f"Query: {query}", style="color: #718096; font-size: 0.85rem; margin-bottom: 10px;"),
                ui.div(f"Method: {method}", style="color: #667eea; font-size: 0.75rem; margin-bottom: 5px;"),
                ui.div(f"Top Match: {top_match['name']}", style="font-weight: 600; margin-bottom: 10px;"),
                ui.div(
                    {"style": "height: 8px; background: #e0e6ed; border-radius: 4px; overflow: hidden;"},
                    ui.div(style=f"width: {score*100}%; height: 100%; background: linear-gradient(90deg, #667eea, #764ba2);")
                ),
                ui.div(f"{score*100:.1f}% match", 
                      style="text-align: right; margin-top: 5px; color: #667eea; font-weight: 600; font-size: 0.85rem;")
            )
        
        return ui.p("Enter a search query to see match scores")
    
    
    # Rating Distribution
    @output
    @render.ui
    def rating_distribution():
        fig = px.histogram(
            restaurants_df,
            x='rating',
            nbins=10,
            title='Distribution of Restaurant Ratings',
            labels={'rating': 'Rating', 'count': 'Number of Restaurants'},
            color_discrete_sequence=['#667eea']
        )
        fig.update_layout(height=300)
        return ui.HTML(fig.to_html(include_plotlyjs='cdn'))
    
    
    # Price Analysis
    @output
    @render.ui
    def price_analysis():
        price_counts = restaurants_df['price_level'].value_counts().sort_index()
        
        fig = go.Figure(data=[
            go.Bar(
                x=['$', '$$', '$$$', '$$$$'][:len(price_counts)],
                y=price_counts.values,
                marker_color='#764ba2'
            )
        ])
        fig.update_layout(
            title='Restaurant Price Distribution',
            xaxis_title='Price Level',
            yaxis_title='Count',
            height=300
        )
        return ui.HTML(fig.to_html(include_plotlyjs='cdn'))
    
    
    # Sentiment Timeline
    @output
    @render.ui
    def sentiment_timeline():
        reviews_with_date = reviews_df.copy()
        reviews_with_date['date'] = pd.to_datetime(reviews_with_date['time'])
        
        sentiment_timeline = reviews_with_date.groupby(
            [pd.Grouper(key='date', freq='M'), 'sentiment']
        ).size().reset_index(name='count')
        
        fig = px.line(
            sentiment_timeline,
            x='date',
            y='count',
            color='sentiment',
            title='Review Sentiment Over Time',
            color_discrete_map={
                'Positive': '#48bb78',
                'Neutral': '#ecc94b',
                'Negative': '#f56565'
            }
        )
        fig.update_layout(height=350)
        return ui.HTML(fig.to_html(include_plotlyjs='cdn'))


# ============================================================================
# CREATE APP
# ============================================================================

app = App(app_ui, server)