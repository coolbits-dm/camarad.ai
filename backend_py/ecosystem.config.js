module.exports = {
  apps : [{
    name   : "camarad",
    script : "python",
    args   : "app.py",
    cwd    : "C:\\grok\\camarad",
    interpreter: "none",
    watch  : true,           // restart la modificare fișiere
    ignore_watch: ["*.db", "*.db-journal", "*.db-wal", "logs", "__pycache__", "*.pyc", "data", "knowledge_base"],
    autorestart: true,
    max_restarts: 10,
    out_file : "./logs/out.log",
    error_file : "./logs/err.log",
    merge_logs : true,
    env: {
      FLASK_ENV: "development",
      PYTHONUNBUFFERED: "true"
    }
  }]
}