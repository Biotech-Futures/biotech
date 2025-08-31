# devops roadmap

## what is devops and purpose in our project
our project requires us to to integrate **DevOps** practice to ensure the **building, testing, deployment and execution** of our software is smooth and consistent.

without **DevOps**, devs made code, passed it to operations, and often ran into production blockers e.g. config mismatches and environment issues. this made releases infrequent, big and risky.

with **DevOps**, devs and ops now share the responsibility to ensuring releasing code into production is safe and consistent. **infrastructure as code (IaC)** means that architecture and environment is versioned, reviewed and automated, and deployments are much more frequent. history allows us to roll back or patch faulty releases.

**DevOps** has a couple of principles:
- automation: removing repetitive manual steps e.g. building, testing and deploying
- continuous integration (CI) - automatically test code change when merged
- continuious delivery/deployment (CD) - automatically deploy code to a staging or prod environment
- **infrastructure as code (IaC)** - we can define servers, networks and databases using config files - such as Docker Compose
- monitoring and feedback

for **our project**, **DevOps** means:
- **Docker & Docker Compose**: everyone can run the same app + DB locally as in staging/prod - a consistent source of truth
- **GitHub Actions (CI/CD)**: every commit / merge builds, tests and can deploy automatically.
- **Staging environment**: set up a realistic environment for client/user acceptance testing (UAT) without touching production
- **OpenAPI/Swagger docs**: automated, up to date API documentation.
- **Config via environment variables**: staging and prod can use the same code with different secrets in different environments.

in a project with potentially many dependencies, it is important to ensure everyone can develop, build and test with the same dependencies installed. using devops allows us to ensure this, avoiding issues like machine mismatch.

## what is docker
**docker**, plainly, is a tool which packages our whole app and everything it needs to run, including:
- **code**
- **dependencies**
- **runtime environment (e.g. java runtime environment)**
- **configs**

it zips all of this up into a single, portable unit called a **container**.

### why docker?
say we didn't have a tool like **docker**. say we install python 3.12, run `pip install Flask`, set up a `MongoClient` (i.e. a nodejs library which handles connections to a mongodb database). 

then, a teammate installs Python 3.10, forgets to install Flask - and the app doesn't work. or, we deploy to a server which has different OS packages itself, and it doesn't work. it **ONLY** works on your machine.

with **docker**, we create a **docker image** and this has exactly the same Python version, Flask version, and other environment variables (e.g. secrets) that you need.

for a teammate, they just need to run `docker run ...` and it works for them too. this also means that we can deploy this same image to staging/prod and it will work reliably.

### key concepts
- **image**: a "blueprint" for the app - holds a snapshot of the code and dependencies for the app
- **container**: a running instance of an instance.
- **Dockerfile**: instructions for building the image, e.g. what python version and packages are we using? what base OS? what command and file to run?
- **Docker Hub / Registry**: a place where we can store images
- **Docker Compose**: we will have multiple containers running different images - e.g. Flask API backend, MongoDB database and frontend - **Compose** can run multiple containers together.

example `Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]
```

then, to execute and run the build, run
```bash
docker build -t <name_of_image> .
```

### docker in our project

for our project:
- **backend container**: runs python + flask
- **frontend container**: runs nginx serving HTML/CSS/JS
- **database container**: runs mongodb database
- **docker compose**: starts all 3 containers with one command