# upload imagery

# list our buckets


s3fs::s3_dir_ls()

path_in <- "/Volumes/backup_2022/backups/new_graph/archive/uav_imagery/imagery_uav_bc"
path_out <- "s3://dev-imagery-uav-bc" 
  
  

# see how big everything is
d_info <- fs::dir_info(
  path,
  recurse = TRUE
  ) |> 
  janitor::adorn_totals(where = "row")

# lets just use aws to load everything into our dev-imagery-uav-bc bucket except the dotfiles
cmd_raw <- paste0(
  "aws s3 sync ", 
  path_in, 
  " ", 
  path_out, 
  " --delete --quiet --exclude */.* --exclude .*"
)

cmd_vector <- unlist(strsplit(cmd_raw, " "))  # Split into vector
cmd <- cmd_vector[1]                      # Extract first element (command)
args_in <- cmd_vector[-1] # Remove first element (arguments only)


processx::run(
  command = cmd,
  args = args_in,
  echo = TRUE,            # Print the command output live
  # wd = path_in, # Set the working directory
  spinner = TRUE        # Show a spinner
  # timeout = 60            # Timeout after 60 seconds
)


s3fs::s3_dir_ls(path_out)


# see files in the bucket
files <- s3fs::s3_dir_ls(path_out, recurse = TRUE) 


# see the website urls
file_urls <- files |> 
  purrr::map(
    ~ ngr::ngr_s3_path_to_https(s3_path = .x, website = F)
  )
