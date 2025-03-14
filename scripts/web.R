library(analogsea)

# spin up a machine
d <- droplet_create(
  image = "rstudio-20-04",
  size = "s-1vcpu-1gb"
)

# see droplets to get the id
analogsea::droplets()

# assign the id
d <- analogsea::droplet(480789025)



# load first two config files and run
d |> 
  droplet_ssh("mkdir -p config") |>
  droplet_upload(
    'scripts/server.sh', 
    "./config/") |>
  droplet_ssh("chmod 0700 config/server.sh") |>
  # run that file
  droplet_ssh("config/server.sh") 

# doing it seperate as this is after the fact
d |> 
  droplet_upload(
    'scripts/certbot.sh', 
    "./config/") |>
  droplet_ssh("chmod 0700 config/certbot.sh") |>
  # run that file
  droplet_ssh("config/certbot.sh") 


# install titiler
d |> 
  droplet_upload(
    'scripts/install_titiler.sh', 
    "./config/") |>
  droplet_ssh("chmod 0700 config/install_titiler.sh") |> 
  # run that file
  droplet_ssh("config/install_titiler.sh")

# add the viewer file
d |> 
  analogsea::droplet_ssh("mkdir -p /var/www/html/viewer") |>
  analogsea::droplet_upload(
    'scripts/viewer.html', 
    "/var/www/html/viewer/") |>
  # these permissions are iimportant so nginx can serve
  analogsea::droplet_ssh("chmod 0755 /var/www/html/viewer") |> 
  analogsea::droplet_ssh("chmod 0644 /var/www/html/viewer/viewer.html") 

# push the viewer.html file to the 

# set up the domain
dom <- analogsea::domains()[[1]]
dom
rec <- analogsea::domain_records(dom)
rec[[5]]$data

# route through www.a11s.one
analogsea::domain_record_update(
  domain_record = rec[[5]], 
  data = analogsea::droplet_ip(d),
  ttl = 1800
)

# this is a11s.one
analogsea::domain_record_create(
  dom, 
  type = "A", 
  name = "@", 
  data = "64.23.157.94", 
  ttl = 1800
)

# create tiles subdomain
analogsea::domain_record_create(
  dom,
  type = "A",
  name = "imagery",
  data = analogsea::droplet_ip(d),  # Replace with droplet object
  ttl = 1800
)

# create tiles subdomain
analogsea::domain_record_create(
  dom,
  type = "A",
  name = "images",
  data = analogsea::droplet_ip(d),  # Replace with droplet object
  ttl = 1800
)

analogsea::domain_record_create(
  dom,
  type = "A",
  name = "tiles",
  data = analogsea::droplet_ip(d),  # Replace with droplet object
  ttl = 1800
)

# for the titiler instance 
analogsea::domain_record_create(
  dom,
  type = "A",
  name = "titiler",
  data = analogsea::droplet_ip(d),  # Replace with droplet object
  ttl = 1800
)

# for the titiler instance accessed via the viewer.html file
analogsea::domain_record_create(
  dom,
  type = "A",
  name = "viewer",
  data = analogsea::droplet_ip(d),  # Replace with droplet object
  ttl = 1800
)

analogsea::domain_record_create(
  dom,
  type = "A",
  name = "rstudio",
  data = analogsea::droplet_ip(d),  # Replace with droplet object
  ttl = 1800
)

# reroute some endpoints

# server {
#   listen 80;
#   server_name a11s.one www.a11s.one;
#   
#   location /tiles/ {
#     proxy_pass http://23cog.s3.amazonaws.com/viewer.html;
#   }
# }
nginx_config <- '
server {
    listen 443 ssl;
    server_name images.a11s.one;

    ssl_certificate /etc/letsencrypt/live/images.a11s.one/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/images.a11s.one/privkey.pem;


    location / {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;

        # add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods GET;
        add_header Access-Control-Allow-Headers Content-Type;
    }
}

server {
    listen 443 ssl;
    server_name rstudio.a11s.one;
    
    ssl_certificate /etc/letsencrypt/live/rstudio.a11s.one/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rstudio.a11s.one/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8787/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}

server {
    listen 443 ssl;
    server_name titiler.a11s.one;
    
    
    ssl_certificate /etc/letsencrypt/live/titiler.a11s.one/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/titiler.a11s.one/privkey.pem;


    location / {
        # if ($request_method = OPTIONS) {
        #         # add_header Access-Control-Allow-Origin "https://viewer.a11s.one" always;
        #         # add_header Access-Control-Allow-Origin * always;
        #         add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        #         add_header Access-Control-Allow-Headers "Content-Type" always;
        #         add_header Content-Length 0;
        #         add_header Content-Type text/plain;
        #         return 204;
        # }
            
        proxy_pass http://127.0.0.1:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;

        # add_header Access-Control-Allow-Origin "https://viewer.a11s.one" always;
        # add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type" always;
    }
}

server {
    listen 443 ssl;
    server_name viewer.a11s.one;
    
    
    ssl_certificate /etc/letsencrypt/live/viewer.a11s.one/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/viewer.a11s.one/privkey.pem;
    
    root /var/www/html/viewer;
    index viewer.html;

    #we match the cors for titiler!
    location / {
        # add_header Access-Control-Allow-Origin "https://titiler.a11s.one" always;
        # add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type" always;
    }
}

server {
    listen 80;
    server_name a11s.one www.a11s.one;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://a11s.one$request_uri;
    }
}

server {
    listen 80;
    server_name images.a11s.one;

    # Allow Certbot to verify the domain
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    return 301 https://images.a11s.one$request_uri;
}

server {
    listen 80;
    server_name rstudio.a11s.one;

    # Allow Certbot to verify the domain
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    return 301 https://rstudio.a11s.one$request_uri;
}


server {
    listen 80;
    server_name titiler.a11s.one;

    # Allow Certbot to verify the domain
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    return 301 https://titiler.a11s.one$request_uri;
}

server {
    listen 80;
    server_name viewer.a11s.one;

    # Allow Certbot to verify the domain
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    return 301 https://viewer.a11s.one$request_uri;
}
'

writeLines(nginx_config, "config/a11s.one")


analogsea::droplet_upload(d, "config/a11s.one", "/etc/nginx/sites-available/a11s.one")
# make a symlink so nginx sees it
analogsea::droplet_ssh(d, "ln -s /etc/nginx/sites-available/a11s.one /etc/nginx/sites-enabled/")
analogsea::droplet_ssh(d, "systemctl restart nginx")

