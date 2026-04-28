import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as ts from "typescript";

const SERVER_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const GENERATED_DIR = path.join(SERVER_DIR, "src/new/drizzle");
const SCHEMA_FILE = path.join(GENERATED_DIR, "schema.ts");
const PUBLIC_SCHEMA_FILE = path.join(GENERATED_DIR, "public.ts");
const ADMIN_SCHEMA_FILE = path.join(GENERATED_DIR, "admin.ts");

type SchemaStatement = {
  name: string;
  text: string;
  schema: "public" | "admin";
};

const sourceText = await readFile(SCHEMA_FILE, "utf8");
const sourceFile = ts.createSourceFile(
  SCHEMA_FILE,
  sourceText,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TS,
);

const importText = sourceFile.statements
  .filter(ts.isImportDeclaration)
  .map((statement) => sourceText.slice(statement.getFullStart(), statement.getEnd()).trim())
  .join("\n");

const statements: SchemaStatement[] = [];

for (const statement of sourceFile.statements) {
  if (!ts.isVariableStatement(statement)) {
    continue;
  }

  const declaration = statement.declarationList.declarations[0];
  if (!declaration || !ts.isIdentifier(declaration.name)) {
    continue;
  }

  const name = declaration.name.text;
  const statementText = sourceText.slice(statement.getFullStart(), statement.getEnd()).trim();
  const initializer = declaration.initializer;
  const initializerText = initializer?.getText(sourceFile) ?? "";
  const schema =
    name === "admin" || initializerText.startsWith("admin.table(")
      ? "admin"
      : "public";

  statements.push({
    name,
    text: statementText,
    schema,
  });
}

if (statements.length === 0) {
  throw new Error(
    `${SCHEMA_FILE} does not look like a freshly generated Drizzle schema file.`,
  );
}

const publicStatements = statements.filter((statement) => statement.schema === "public");
const adminStatements = statements.filter((statement) => statement.schema === "admin");

const publicNames = publicStatements.map((statement) => statement.name);
const adminNames = adminStatements.map((statement) => statement.name);

const publicImports = referencedNames(publicStatements, adminNames);
const adminImports = referencedNames(adminStatements, publicNames);

await mkdir(GENERATED_DIR, { recursive: true });
await writeFile(
  PUBLIC_SCHEMA_FILE,
  buildSchemaFile(importText, publicImports, "./admin", publicStatements),
);
await writeFile(
  ADMIN_SCHEMA_FILE,
  buildSchemaFile(importText, adminImports, "./public", adminStatements),
);
await writeFile(SCHEMA_FILE, 'export * from "./public";\nexport * from "./admin";\n');

console.log(
  `Split pulled Drizzle schema into public.ts (${publicStatements.length}) and admin.ts (${adminStatements.length}).`,
);

function referencedNames(
  statementsToSearch: SchemaStatement[],
  candidateNames: string[],
): string[] {
  const body = statementsToSearch.map((statement) => statement.text).join("\n");

  return candidateNames
    .filter((name) => new RegExp(`\\b${escapeRegExp(name)}\\b`).test(body))
    .sort();
}

function buildSchemaFile(
  imports: string,
  crossSchemaImports: string[],
  crossSchemaPath: string,
  schemaStatements: SchemaStatement[],
): string {
  const crossImport =
    crossSchemaImports.length > 0
      ? `import { ${crossSchemaImports.join(", ")} } from "${crossSchemaPath}";\n`
      : "";

  return `${imports}\n${crossImport}\n${schemaStatements
    .map((statement) => statement.text)
    .join("\n\n")}\n`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
