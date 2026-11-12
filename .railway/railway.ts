import {
  bucket,
  defineRailway,
  github,
  postgres,
  project,
  service,
} from "railway/iac";

// Optional CLI provisioning; the equivalent dashboard steps are in docs/deploy-railway.md.
// Set JWT_SECRET, OPENAI_API_KEY, OPENAI_MODEL and APP_ORIGIN as shared variables first.
export default defineRailway((ctx) => {
  const repository = "RafaelTaves/OtimizadorCurriculosTCC";
  const db = postgres("Postgres");
  const files = bucket("curriculos", { region: "iad" });
  const backendSource = () =>
    github(repository, { branch: "production", rootDirectory: "/api" });
  const deploy = {
    sleepApplication: false,
    restartPolicyType: "ON_FAILURE" as const,
    restartPolicyMaxRetries: 10,
  };
  const shared = {
    DATABASE_URL: db.env.DATABASE_URL,
    JWT_SECRET: ctx.shared.JWT_SECRET,
    STORAGE_BACKEND: "s3",
    S3_BUCKET: "${{curriculos.BUCKET}}",
    S3_ENDPOINT_URL: "${{curriculos.ENDPOINT}}",
    S3_REGION: "${{curriculos.REGION}}",
    S3_ACCESS_KEY_ID: "${{curriculos.ACCESS_KEY_ID}}",
    S3_SECRET_ACCESS_KEY: "${{curriculos.SECRET_ACCESS_KEY}}",
    S3_ADDRESSING_STYLE: "virtual",
    PYTHONUNBUFFERED: "1",
  };
  const ai = {
    OPENAI_API_KEY: ctx.shared.OPENAI_API_KEY,
    OPENAI_MODEL: ctx.shared.OPENAI_MODEL,
  };
  const api = service("api", {
    deploy,
    source: backendSource(),
    preDeploy: "alembic upgrade head",
    healthcheck: "/ready",
    healthcheckTimeout: 120,
    replicas: 1,
    env: { ...shared, ...ai, PORT: "8000" },
  });
  const workerAI = service("worker-ai", {
    deploy,
    source: backendSource(),
    start: "python -m app.worker --lane ai",
    replicas: 1,
    env: { ...shared, ...ai },
  });
  const workerPDF = service("worker-pdf", {
    deploy,
    source: backendSource(),
    replicas: 1,
    env: {
      ...shared,
      RAILWAY_DOCKERFILE_PATH: "docker/railway-pdf.Dockerfile",
      COMPILER_BACKEND: "sandbox",
    },
  });
  const front = service("front", {
    deploy,
    source: github(repository, {
      branch: "production",
      rootDirectory: "/front",
    }),
    healthcheck: "/login",
    replicas: 1,
    env: {
      PORT: "3000",
      APP_ORIGIN: ctx.shared.APP_ORIGIN,
      API_BASE_URL: "http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000",
    },
  });
  return project("otimizador-curriculos", {
    resources: [db, files, api, workerAI, workerPDF, front],
  });
});
