// api/src/queries/queries.service.ts
import { Injectable } from '@nestjs/common';
import { execa } from 'execa';
import * as path from 'node:path';
import * as fs from 'node:fs';

function findRepoRoot(startDir: string): string {
  let dir = startDir;
  for (let i = 0; i < 5; i++) {
    const candidate = path.join(dir, 'worker_py', 'app', 'run_query.py');
    if (fs.existsSync(candidate)) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error(`Cannot find worker_py/app/run_query.py from ${startDir}`);
}

@Injectable()
export class QueriesService {
  async runPrompt(prompt: string) {
    const pythonBin = process.env.PYTHON_BIN || 'python3';
    const runnerRel = process.env.PY_RUNNER || path.join('worker_py', 'app', 'run_query.py');

    const repoRoot = findRepoRoot(process.cwd());
    const runner = path.resolve(repoRoot, runnerRel);

    // Only forward those secrets if they exist
    const env: NodeJS.ProcessEnv = { ...process.env };
    if (!process.env.SEC_API_KEY) delete env.SEC_API_KEY;
    if (!process.env.EDGAR_IDENTITY) delete env.EDGAR_IDENTITY;
    if (!process.env.OPENAI_API_KEY) delete env.OPENAI_API_KEY;

    const { stdout } = await execa(pythonBin, [runner, '--prompt', prompt], {
      env,
      cwd: repoRoot,
      timeout: 1000 * 60 * 6,
    });

    try { return JSON.parse(stdout); }
    catch { return { ok: false, error: 'Worker did not return JSON', raw: stdout }; }
  }
}
