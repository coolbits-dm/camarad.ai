# Deploy Guide (Ubuntu 24.04 + Nginx + PM2)

## 1) Server bootstrap

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx
sudo npm i -g pm2
```

## 2) App setup

```bash
sudo mkdir -p /var/www
cd /var/www
sudo git clone <YOUR_REPO_URL> camarad
sudo chown -R $USER:$USER /var/www/camarad
cd /var/www/camarad
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3) Environment

Create `.env` (or export env vars):

```bash
export SECRET_KEY="change-me"
export GROK_API_KEY="..."
export DEBUG="0"
export HOST="127.0.0.1"
export PORT="8000"
```

## 4) PM2 production

```bash
cd /var/www/camarad
pm2 start ecosystem.production.config.js
pm2 save
pm2 startup
```

## 5) Nginx

```bash
sudo cp deploy/nginx/camarad.conf /etc/nginx/sites-available/camarad
sudo ln -s /etc/nginx/sites-available/camarad /etc/nginx/sites-enabled/camarad
sudo nginx -t
sudo systemctl restart nginx
```

## 6) SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## 7) Backup before updates

```bash
cd /var/www/camarad
bash deploy/scripts/backup.sh
```

## 8) Update flow

```bash
cd /var/www/camarad
git pull
source venv/bin/activate
pip install -r requirements.txt
pm2 restart camarad
```
