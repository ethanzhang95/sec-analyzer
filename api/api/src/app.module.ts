import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ThrottlerModule } from '@nestjs/throttler';
import { QueriesModule } from './queries/queries.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),      // loads environment variables
    ThrottlerModule.forRoot([{ ttl: 60, limit: 30 }]), // 30 requests/minute
    QueriesModule,                                  // our feature module
  ],
})
export class AppModule {}
