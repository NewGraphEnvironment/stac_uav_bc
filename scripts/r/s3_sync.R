# upload imagery

# list our buckets


s3fs::s3_dir_ls()

path_in <- "/Volumes/backup_2022/backups/new_graph/archive/uav_imagery/imagery_uav_bc/"
path_out <- "s3://dev-imagery-uav-bc" 
  
  

# see how big everything is
d_info <- fs::dir_info(
  path,
  recurse = TRUE
  ) |> 
  janitor::adorn_totals(where = "row")

# lets just use aws to load everything into our dev-imagery-uav-bc bucket
# aws s3 sync /Volumes/backup_2022/backups/new_graph/archive/uav_imagery/imagery_uav_bc s3://dev-imagery-uav-bc --delete --quiet

# because we are ogin inside the root directory we are calling "." to capture all the subdirectories there!!
cmd_raw <- "aws s3 sync . s3://dev-imagery-uav-bc --delete --quiet"
cmd_vector <- unlist(strsplit(cmd_raw, " "))  # Split into vector
cmd <- cmd_vector[1]                      # Extract first element (command)
args_in <- c(cmd_vector[-1])                     # Remove first element (arguments only)

# we want to work from inside the sync folder to get the subdirectories as our first level in our buckt
processx::run(
  command = cmd,
  args = args_in,
  echo = TRUE,            # Print the command output live
  wd = path_in, # Set the working directory
  spinner = TRUE        # Show a spinner
  # timeout = 60            # Timeout after 60 seconds
)
