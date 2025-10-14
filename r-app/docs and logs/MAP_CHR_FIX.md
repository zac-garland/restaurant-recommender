# map_chr Function Fix

## Problem
The app was showing errors related to the `map_chr` function not being found:
```
Warning: Error in mutate: i In argument: `combined_text = paste(name, coalesce(cuisine, ""),
  coalesce(text, "")) %>% map_chr(preprocess_text)`.
Caused by error in `map_chr()`:
! could not find function "map_chr"
```

## Root Cause
The `map_chr` function is part of the `purrr` package, which was not explicitly loaded. While `purrr` was being loaded as part of the `tidymodels` meta-package, it wasn't directly available in the namespace.

## Solution
Added `purrr` to the explicit library imports:

```r
# Load specific tidymodels packages to avoid infer conflicts
library(purrr)  # Added this line
library(parsnip)
library(workflows)
library(tune)
library(yardstick)
```

## Testing Results
✅ **map_chr function working**: Successfully processes text vectors
✅ **TF-IDF calculation working**: Returns 3566 restaurants for "italian" search
✅ **App responding**: HTTP 200 from http://127.0.0.1:3838
✅ **No more map_chr errors**: All mutate operations with map_chr now work

## Functions That Use map_chr
- `calculate_tfidf_scores()`: Uses `map_chr(preprocess_text)` to clean text data
- `preprocess_text()`: Text cleaning function applied via map_chr
- All text processing in the TF-IDF pipeline

## Files Modified
- `r-app/app.R`: Added `library(purrr)` to imports

## Status
**RESOLVED** - The `map_chr` function is now available and all text processing functionality works correctly.
