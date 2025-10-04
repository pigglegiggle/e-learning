# E-Learning Platform
[![E-Learning](https://img.shields.io/badge/E--Learning-1.0-blue?style=for-the-badge&logo=education)](https://your-website-or-link.com)

A web-based e-learning platform built with Python FastAPI and MySQL.

## Prerequisites

- Docker
- Docker Compose

## Setup Instructions

1. Clone the repository and navigate to the project directory
2. Create a `.env` file in the root directory with the following variables:
   ```bash
      # Database Configuration
      DB_HOST=localhost
      DB_PORT=3306
      DB_USER=root
      DB_PASSWORD=
      DB_NAME=elearning
      
      # MySQL Root Password (for Docker)
      MYSQL_ROOT_PASSWORD=
      
      # Application Configuration
      APP_HOST=0.0.0.0
      APP_PORT=8000
      DEBUG=True
      
      # Security
      SECRET_KEY=your-secret-key-here-change-in-production
   ```
   Note: For development, you can leave these as default values or customize as needed.
3. Build and start the containers:
   ```bash
   docker-compose up -d --build
   ```

The application will be available at `http://localhost:8000`

## Docker Services

- **web**: FastAPI application running on port 8000
- **db**: MySQL database running on port 3306

## Database

The MySQL database will be automatically initialized with the schema defined in `schema.sql`.

### Database Access

You can connect to the MySQL database using:
- **Host**: localhost
- **Port**: 3306
- **Database**: elearning
- **Username**: root
- **Password**: (empty)

## Development

To stop the containers:
```bash
docker-compose down
```

To rebuild after code changes:
```bash
docker-compose up -d --build
```

To view logs:
```bash
docker-compose logs web
docker-compose logs db
```

## Project Structure

```
├── docker-compose.yml      # Docker services configuration
├── Dockerfile             # Python application container
├── main.py                # FastAPI application
├── requirements.txt       # Python dependencies
├── schema.sql            # Database schema
├── static/               # Static HTML files
└── .env                  # Environment variables (create this file)
```
