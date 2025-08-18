import { ApiProperty } from '@nestjs/swagger';
import { IsString, MinLength } from 'class-validator';

export class CreateQueryDto {
  @ApiProperty({ example: "What is Apple's net income for FY 2022?" })
  @IsString() @MinLength(3)
  prompt!: string;
}