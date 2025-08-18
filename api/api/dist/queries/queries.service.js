"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.QueriesService = void 0;
const common_1 = require("@nestjs/common");
const execa_1 = require("execa");
const path = __importStar(require("node:path"));
const fs = __importStar(require("node:fs"));
function findRepoRoot(startDir) {
    let dir = startDir;
    for (let i = 0; i < 5; i++) {
        const candidate = path.join(dir, 'worker_py', 'app', 'run_query.py');
        if (fs.existsSync(candidate))
            return dir;
        const parent = path.dirname(dir);
        if (parent === dir)
            break;
        dir = parent;
    }
    throw new Error(`Cannot find worker_py/app/run_query.py from ${startDir}`);
}
let QueriesService = class QueriesService {
    async runPrompt(prompt) {
        const pythonBin = process.env.PYTHON_BIN || 'python3';
        const runnerRel = process.env.PY_RUNNER || path.join('worker_py', 'app', 'run_query.py');
        const repoRoot = findRepoRoot(process.cwd());
        const runner = path.resolve(repoRoot, runnerRel);
        const env = { ...process.env };
        if (!process.env.SEC_API_KEY)
            delete env.SEC_API_KEY;
        if (!process.env.EDGAR_IDENTITY)
            delete env.EDGAR_IDENTITY;
        if (!process.env.OPENAI_API_KEY)
            delete env.OPENAI_API_KEY;
        const { stdout } = await (0, execa_1.execa)(pythonBin, [runner, '--prompt', prompt], {
            env,
            cwd: repoRoot,
            timeout: 1000 * 60 * 6,
        });
        try {
            return JSON.parse(stdout);
        }
        catch {
            return { ok: false, error: 'Worker did not return JSON', raw: stdout };
        }
    }
};
exports.QueriesService = QueriesService;
exports.QueriesService = QueriesService = __decorate([
    (0, common_1.Injectable)()
], QueriesService);
//# sourceMappingURL=queries.service.js.map