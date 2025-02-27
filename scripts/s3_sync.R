# upload imagery

# list our buckets


# s3fs::s3_dir_ls()

path_in <- "/Users/airvine/Projects/gis/uav_imagery/imagery_uav_bc"
path_out <- "s3://dev-imagery-uav-bc" 
  
################################################################################################################
#--------------------------------------------------backup everything---------------------------------------------------
################################################################################################################
# path_in <- "/Volumes/backup_2022/backups/new_graph/uav_imagery"
# path_out <- "s3://dev-backup-imagery-uav" 

# see how big everything is
# d_info_in <- fs::dir_info(
#   path_in,
#   recurse = TRUE
#   ) |> 
#   janitor::adorn_totals(where = "row")

# lets just use aws to load everything into our dev-imagery-uav-bc bucket except the dotfiles
cmd_raw <- paste0(
  "aws s3 sync ", 
  path_in, 
  " ", 
  path_out, 
  # we have set our multipart chunksize and concurrent requests in our ~/.aws/config file under profile airvine then 
  # add  export AWS_PROFILE=airvine to our ~/.bashrc file. thats why we call a profile here
  " --delete --quiet --exclude */.* --exclude .* --profile airvine"
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


# to stop the computer from sleeping we ran the following in  the terminal
# caffeinate -s Rscript /Users/airvine/Projects/repo/stac_uav_bc/scripts/r/s3_sync.R
  

