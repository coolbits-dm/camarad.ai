module.exports = {
  apps: [
    {
      name: "camarad",
      script: "app.py",
      interpreter: "python3",
      cwd: "/var/www/camarad",
      watch: false,
      autorestart: true,
      max_restarts: 5,
      max_memory_restart: "600M",
      instances: 1,
      exec_mode: "fork",
      out_file: "/var/log/camarad/out.log",
      error_file: "/var/log/camarad/err.log",
      merge_logs: true,
      env: {
        PYTHONUNBUFFERED: "true",
        DEBUG: "0",
        HOST: "127.0.0.1",
        PORT: "8000"
      }
    }
  ]
};
