library(lubridate)
library(dplyr)

relative_time_description <- function(date) {
  if (is.na(date)) return(NA_character_)

  date <- as.Date(date)
  today <- Sys.Date()

  # Calculate intervals
  diff <- interval(date, today)

  # Future dates (negative interval)
  if (date > today) {
    diff <- interval(today, date)

    days <- as.numeric(diff, "days")
    months <- as.numeric(diff, "months")
    years <- as.numeric(diff, "years")

    if (days <= 7) return("in the next week")
    if (months < 1) return("in the next month")
    if (years < 1) {
      m <- round(months)
      return(paste("in", m, ifelse(m == 1, "month", "months")))
    }
    y <- round(years)
    return(paste("in", y, ifelse(y == 1, "year", "years")))
  }

  # Past dates
  days <- as.numeric(diff, "days")
  months <- as.numeric(diff, "months")
  years <- as.numeric(diff, "years")

  if (days <= 7) return("in the last week")

  if (years < 1) {
    m <- round(months)
    if (m == 1) return("a month ago")
    return(paste(m, "months ago"))
  }

  y <- round(years)
  if (y == 1) return("a year ago")
  return(paste(y, "years ago"))
}

parse_new_review <- function(review){
  review <- read_html(HTML(review))

  tibble(
    author_name = html_nodes(review,".comment-author") %>% html_text(),
    language = "en",
    original_language = "en",
    profile_photo_url = NA_character_,
    rating = html_nodes(review,".google_stars") %>% html_nodes("div") %>% html_attr("style") %>% str_extract("\\d+") %>% as.double() %>% {(./100)*5},
    relative_time_description = html_nodes(review,"time") %>% html_text() %>% str_split("on") %>% unlist() %>% .[[1]],
    text = html_nodes(review,".comment-text") %>% html_text() %>% paste(collapse = "\n"),
    translated = FALSE
  )

}


backup_reviews <- list.files(path.expand("~/Downloads/claude-tji/backups"),full.names = TRUE) %>% map_dfr(~{read_csv(.x,col_types = cols(
  input_query = col_character(),
  restaurant_name = col_character(),
  restaurant_url = col_character(),
  match_score = col_double(),
  comment_html = col_character(),
  comment_text = col_character(),
  scraped_at = col_datetime(format = "")
))}) %>%
  rename(name = input_query) %>%
  filter(!str_detect(restaurant_name,"•")) %>%
  left_join(read_csv('data/restaurants.csv') %>% distinct(id,name)) %>%
  filter(!is.na(id))


backup_reviews %>%
  filter(match_score < 1) %>%
  distinct(name,restaurant_name,match_score) %>%
  arrange(match_score) %>%
  print(n = nrow(.))

old_reviews %>%
  glimpse()


library(furrr)

plan(multisession)

tictoc::tic()
new_backup_revs <- backup_reviews %>%
  select(id,comment_html) %>%
  # rowwise() %>%
  mutate(new_tbl_data = map(comment_html,parse_new_review)) %>% unnest(new_tbl_data)
tictoc::toc()

new_backup_revs %>% mutate(text = str_trim(text) %>% str_squish()) %>%
  select(names(old_reviews))


upsert <- new_backup_revs %>%
  mutate(time = as.numeric(my(relative_time_description)) * 86400) %>%
  mutate(author_url = NA_character_) %>%
  select(names(old_reviews))


library(DBI)
library(RSQLite)

# Connect to the database
con <- dbConnect(RSQLite::SQLite(), "austin_restaurants.db")

# Insert the data
dbWriteTable(con, "reviews", upsert, append = TRUE)

# Disconnect
dbDisconnect(con)






