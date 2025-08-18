import { QueriesService } from './queries.service';
import { CreateQueryDto } from './dto';
export declare class QueriesController {
    private readonly svc;
    constructor(svc: QueriesService);
    health(): {
        ok: boolean;
    };
    create(dto: CreateQueryDto): Promise<any>;
}
