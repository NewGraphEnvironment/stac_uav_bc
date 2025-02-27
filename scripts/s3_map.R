path_out <- "s3://dev-imagery-uav-bc" 
# path_out <- "s3://dev-backup-imagery-uav" 
s3fs::s3_dir_ls(path_out, recurse = T )

d_info_out <- s3fs::s3_dir_info(path_out,
                  recurse = TRUE
) |> 
  janitor::adorn_totals(where = "row")

# see files in the bucket
files <- s3fs::s3_dir_ls(path_out, recurse = TRUE) 


# see the website urls
file_urls <- files |> 
  purrr::map(
    ~ ngr::ngr_s3_path_to_https(s3_path = .x, website = FALSE)
  )

# create the links with the tileserver

file_urls_tiles <- paste0(
  "http:/23cog.s3.amazonaws.com/viewer.html?cog=",
  file_urls
)

# these are the raw json locations
grep(".json", file_urls, value = TRUE)

# search by keyword
grep("station", file_urls, value = TRUE)
