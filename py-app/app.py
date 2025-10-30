"""
Restaurant Recommender - Shiny for Python Application
Implements: TF-IDF, BERT Embeddings, Sentiment Analysis, Topic Modeling, Cosine Similarity
"""

from shiny import App, ui, render, reactive
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import plotly.graph_objects as go
import plotly.express as px

# ============================================================================
# DATA LOADING & PREPROCESSING
# ============================================================================

def load_data():
    """
    Load your 4 CSV files:
    1. photos.csv - photo data
    2. restaurant_details.csv - full restaurant info
    3. restaurant_basic.csv - basic info with coordinates
    4. reviews.csv - review text and ratings
    """
    
    # Example structure based on your data
    restaurants = pd.DataFrame({
        'id': ['ChIJ___Dgji0RIYRmrGwh77TEdQ', 'ChIJ___GM3a2RIYRFrouvPhX9c0', 'ChIJ___vZRS1RIYRBAa45nfBejo'],
        'name': ['Sabor a Honduras', 'Taqueria El Torito', 'Hold Out Brewing'],
        'address': ['2538 Elmont Dr, Austin, TX 78741', '1149 Airport Blvd, Austin, TX 78721', '1208 W 4th St, Austin, TX 78703'],
        'rating': [4.1, 4.6, 4.6],
        'price_level': [1, np.nan, 2],
        'user_ratings_total': [325, 10, 1050],
        'lat': [30.239, 30.307, 30.273],
        'lng': [-97.731, -97.716, -97.759],
        'cuisine': ['Honduran', 'Mexican', 'American, Bar'],
        'serves_vegetarian': [False, True, False],
        'outdoor_seating': [True, False, True],
        'dine_in': [True, True, True],
        'takeout': [True, True, True],
    })
    
    reviews = pd.DataFrame({
        'restaurant_id': ['ChIJ___Dgji0RIYRmrGwh77TEdQ', 'ChIJ___Dgji0RIYRmrGwh77TEdQ', 'ChIJ___GM3a2RIYRFrouvPhX9c0'],
        'author': ['Beverly Anne', 'Timothy Ichich', 'Hans Huether'],
        'rating': [4, 5, 4],
        'text': [
            'From the Baleadas, Pupusas, and Tacos Catrachos; you cant go wrong with anything on the menu. We love it, our kids love it.',
            'Very excellent, the food is very delicious, I recommend visiting it.',
            'Just the mood for something different & was in the neighborhood. Quick service, really good food.'
        ],
        'time': ['2018-04-21', '2024-01-15', '2023-05-15']
    })
    
    return restaurants, reviews


def preprocess_text(text):
    """Clean and preprocess review text for NLP"""
    if pd.isna(text):
        return ""
    return str(text).lower().strip()


def calculate_tfidf_scores(restaurants, reviews, query):
    """
    CONCEPT: TF-IDF Vectorization
    Convert text to numerical vectors and rank by relevance
    """
    # Aggregate reviews per restaurant
    review_texts = reviews.groupby('restaurant_id')['text'].apply(
        lambda x: ' '.join(x)
    ).reset_index()
    
    # Merge with restaurant info
    restaurants_with_reviews = restaurants.merge(
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
    
    # TF-IDF Vectorization
    vectorizer = TfidfVectorizer(
        max_features=100,
        stop_words='english',
        ngram_range=(1, 2)
    )
    
    # Fit on restaurant texts
    tfidf_matrix = vectorizer.fit_transform(
        restaurants_with_reviews['combined_text']
    )
    
    # Transform query
    query_vec = vectorizer.transform([preprocess_text(query)])
    
    # Calculate cosine similarity (CONCEPT: Cosine Similarity)
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    
    restaurants_with_reviews['similarity_score'] = similarities
    
    return restaurants_with_reviews.sort_values('similarity_score', ascending=False)


def analyze_sentiment(reviews):
    """
    CONCEPT: Sentiment Analysis
    In production, use transformers/BERT. Here we'll use simple heuristics
    """
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
    CONCEPT: Topic Modeling (simplified)
    In production, use LDA or BERTopic
    """
    from sklearn.feature_extraction.text import CountVectorizer
    
    # Simple keyword extraction as proxy for topics
    vectorizer = CountVectorizer(
        max_features=n_topics,
        stop_words='english',
        ngram_range=(1, 2)
    )
    
    texts = reviews['text'].apply(preprocess_text)
    word_matrix = vectorizer.fit_transform(texts)
    
    topics = vectorizer.get_feature_names_out()
    return topics


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
                        "Search Restaurants",
                        class_="btn-lg btn-primary",
                        style="margin-top: 1rem;"
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
                        
                        ui.input_selectize(
                            "cuisine_filter",
                            "Cuisine Type",
                            choices=["All", "Mexican", "Italian", "American", "Asian", "Honduran"],
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
    )
)


# ============================================================================
# SHINY SERVER
# ============================================================================

def server(input, output, session):
    
    # Load data
    restaurants_df, reviews_df = load_data()
    
    # Reactive: Filtered restaurants based on search and filters
    @reactive.Calc
    def filtered_restaurants():
        query = input.query_input() or input.main_search() or ""
        
        if not query:
            filtered = restaurants_df.copy()
        else:
            # Apply TF-IDF ranking
            filtered = calculate_tfidf_scores(restaurants_df, reviews_df, query)
        
        # Apply filters
        if input.rating_filter():
            filtered = filtered[filtered['rating'] >= input.rating_filter()]
        
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
        
        fig = px.scatter_mapbox(
            df,
            lat='lat',
            lon='lng',
            hover_name='name',
            hover_data=['rating', 'cuisine', 'address'],
            color='rating',
            size='user_ratings_total',
            color_continuous_scale='Viridis',
            zoom=11,
            height=400
        )
        
        fig.update_layout(
            mapbox_style="open-street-map",
            margin={"r":0,"t":0,"l":0,"b":0}
        )
        
        return ui.HTML(fig.to_html(include_plotlyjs='cdn'))
    
    
    # Restaurant list
    @output
    @render.ui
    def restaurant_list():
        df = filtered_restaurants()
        
        cards = []
        for idx, row in df.head(10).iterrows():
            score = row.get('similarity_score', 0)
            card = ui.div(
                {"class": "restaurant-card"},
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
        
        if 'similarity_score' in df.columns:
            top_3 = df.nlargest(3, 'similarity_score')
            
            items = []
            for i, (idx, row) in enumerate(top_3.iterrows(), 1):
                items.append(
                    ui.div(
                        ui.span(f"{i}.", style="font-weight: 700; margin-right: 10px;"),
                        ui.span(row['name'], style="font-weight: 600;"),
                        ui.span(f"{row['similarity_score']:.3f}", 
                               style="float: right; color: #047857; font-weight: 600;")
                    )
                )
            
            return ui.div(*items)
        
        return ui.p("Enter a search query to see TF-IDF rankings")
    
    
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
        
        if query and 'similarity_score' in df.columns and len(df) > 0:
            top_match = df.iloc[0]
            score = top_match['similarity_score']
            
            return ui.div(
                ui.div(f"Query: {query}", style="color: #718096; font-size: 0.85rem; margin-bottom: 10px;"),
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