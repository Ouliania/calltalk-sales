module.exports = {
  apps: [
    {
      name: 'trigga-okocrm-sync',
      script: './trigga_okocrm_sync.js',
      args: '--daemon',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      env: {
        NODE_ENV: 'production',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: './error.log',
      out_file: './sync.log',
      merge_logs: true,
    },
  ],
};
