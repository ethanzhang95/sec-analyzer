import { Body, Controller, Get, HttpException, Post } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { QueriesService } from './queries.service';
import { CreateQueryDto } from './dto';

@ApiTags('queries')
@Controller('queries')
export class QueriesController {
  constructor(private readonly svc: QueriesService) {}

  @Get('health')
  health() {
    return { ok: true };
  }

  @Post()
  async create(@Body() dto: CreateQueryDto) {
    const res = await this.svc.runPrompt(dto.prompt);
    if (!res?.ok) {
      throw new HttpException(res?.error ?? 'Worker error', 500);
    }
    return res; // { ok, answer, citations }
  }
}
