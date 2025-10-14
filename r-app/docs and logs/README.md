# Restaurant Recommender - R Shiny Version

A powerful restaurant recommendation system built with R Shiny, featuring advanced NLP and machine learning capabilities.

## Features

### 🎯 **Advanced Search & Similarity**
- **TF-IDF Vectorization**: Fast keyword-based similarity matching
- **BERT Embeddings**: Semantic understanding (planned for future implementation)
- **Smart Fallback**: Name-based matching when TF-IDF fails
- **Complete Dataset**: Uses all 3,566 restaurants and 16,509 reviews

### 😊 **Sentiment Analysis**
- **Rating-based Sentiment**: Categorizes reviews as Positive/Neutral/Negative
- **BERT Integration**: Ready for advanced sentiment analysis (future enhancement)
- **Visual Analytics**: Interactive sentiment distribution charts

### 🏷️ **Topic Modeling**
- **LDA (Latent Dirichlet Allocation)**: Discovers meaningful restaurant themes
- **Dynamic Topics**: Extracts topics from review text
- **Visual Display**: Topic keywords with modern UI

### 📊 **Interactive Analytics**
- **Restaurant Map**: Interactive Leaflet map with restaurant locations
- **Rating Distribution**: Histogram of restaurant ratings
- **Price Analysis**: Distribution across price levels
- **Sentiment Timeline**: Review sentiment trends over time

## Technology Stack

### Core R Packages
- **shiny**: Web application framework
- **shinydashboard**: Enhanced UI components
- **DT**: Interactive data tables
- **plotly**: Interactive visualizations
- **leaflet**: Interactive maps

### Data & Analysis
- **tidyverse**: Data manipulation (dplyr, tidyr, stringr)
- **DBI/RSQLite**: Database connectivity
- **tidymodels**: Machine learning framework
- **textrecipes**: Text preprocessing for ML

### NLP & Text Analysis
- **topicmodels**: LDA topic modeling
- **text**: Advanced text analysis
- **tm**: Text mining utilities
- **wordcloud2**: Word cloud visualizations

## Installation

### 1. Install R Packages
```r
# Run the installation script
source("install_packages.R")
```

### 2. Verify Database
Ensure the SQLite database exists:
```
../austin_restaurants.db
```

### 3. Run the Application
```r
# Start the Shiny app
shiny::runApp("app.R")
```

Or from command line:
```bash
Rscript -e "shiny::runApp('app.R', port=3838)"
```

## Usage

### 🔍 **Search Functionality**
1. **Enter Search Query**: Try "barbecue", "Italian", "pizza", "romantic dinner"
2. **Select Similarity Method**: Choose between TF-IDF (fast) or BERT (semantic)
3. **Apply Filters**: Rating, cuisine type, dietary preferences, amenities
4. **View Results**: Interactive map and ranked restaurant list

### 📊 **Analytics Dashboard**
- **Rating Distribution**: See overall restaurant quality distribution
- **Price Analysis**: Understand price level distribution
- **Sentiment Timeline**: Track review sentiment trends over time

### 🎛️ **Interactive Features**
- **Restaurant Map**: Click markers for detailed information
- **Similarity Scores**: See how well restaurants match your query
- **Topic Keywords**: Discover common themes in reviews
- **Sentiment Breakdown**: Visual sentiment analysis results

## Key Improvements Over Python Version

### 🚀 **Performance**
- **Native R Integration**: Better performance with R's data structures
- **Efficient Processing**: Optimized for R's vectorized operations
- **Memory Management**: Better handling of large datasets

### 🔧 **Flexibility**
- **Easy Customization**: R's functional programming makes tweaking easier
- **Package Ecosystem**: Access to R's extensive ML and NLP packages
- **Statistical Analysis**: Built-in statistical functions and tests

### 📈 **Analytics**
- **Advanced Visualizations**: ggplot2 and plotly integration
- **Statistical Models**: Easy integration with R's modeling packages
- **Reproducible Research**: R Markdown integration ready

## Architecture

### Data Flow
```
SQLite Database → DBI Connection → dplyr Processing → Shiny Reactive
```

### Similarity Calculation
```
Query → Text Preprocessing → TF-IDF Vectorization → Cosine Similarity → Ranking
```

### Topic Modeling
```
Reviews → Text Cleaning → Document-Term Matrix → LDA → Topic Extraction
```

## Future Enhancements

### 🤖 **Advanced NLP**
- **BERT Integration**: Implement BERT embeddings for semantic similarity
- **Advanced Sentiment**: Use transformers package for better sentiment analysis
- **Named Entity Recognition**: Extract restaurant features automatically

### 📊 **Enhanced Analytics**
- **Clustering Analysis**: Group similar restaurants
- **Recommendation Engine**: Collaborative filtering
- **Predictive Modeling**: Predict restaurant success factors

### 🎨 **UI/UX Improvements**
- **Advanced Filtering**: More sophisticated filter options
- **Personalization**: User preference learning
- **Mobile Optimization**: Responsive design improvements

## Troubleshooting

### Common Issues

1. **Package Installation Errors**
   ```r
   # Update R and try again
   update.packages()
   install.packages("devtools")
   ```

2. **Database Connection Issues**
   ```r
   # Check database path
   file.exists("../austin_restaurants.db")
   ```

3. **Memory Issues with Large Datasets**
   ```r
   # Increase memory limit
   options(shiny.maxRequestSize = 100*1024^2)
   ```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Built with ❤️ using R Shiny, tidyverse, and tidymodels**
