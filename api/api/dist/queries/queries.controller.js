"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.QueriesController = void 0;
const common_1 = require("@nestjs/common");
const swagger_1 = require("@nestjs/swagger");
const queries_service_1 = require("./queries.service");
const dto_1 = require("./dto");
let QueriesController = class QueriesController {
    svc;
    constructor(svc) {
        this.svc = svc;
    }
    health() {
        return { ok: true };
    }
    async create(dto) {
        const res = await this.svc.runPrompt(dto.prompt);
        if (!res?.ok) {
            throw new common_1.HttpException(res?.error ?? 'Worker error', 500);
        }
        return res;
    }
};
exports.QueriesController = QueriesController;
__decorate([
    (0, common_1.Get)('health'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", void 0)
], QueriesController.prototype, "health", null);
__decorate([
    (0, common_1.Post)(),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [dto_1.CreateQueryDto]),
    __metadata("design:returntype", Promise)
], QueriesController.prototype, "create", null);
exports.QueriesController = QueriesController = __decorate([
    (0, swagger_1.ApiTags)('queries'),
    (0, common_1.Controller)('queries'),
    __metadata("design:paramtypes", [queries_service_1.QueriesService])
], QueriesController);
//# sourceMappingURL=queries.controller.js.map