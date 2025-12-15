// PM2 Ecosystem Configuration for Cloudflare Pages Development
module.exports = {
  apps: [
    {
      name: 'cv-pathfinding-app',
      script: 'npx',
      args: 'wrangler pages dev dist --ip 0.0.0.0 --port 3000',
      cwd: '/home/user/webapp',
      env: {
        NODE_ENV: 'development',
        PORT: 3000
      },
      watch: false, // Disable PM2 file monitoring (wrangler handles hot reload)
      instances: 1, // Development mode uses only one instance
      exec_mode: 'fork',
      restart_delay: 3000,
      max_restarts: 10,
      min_uptime: '10s'
    }
  ]
}