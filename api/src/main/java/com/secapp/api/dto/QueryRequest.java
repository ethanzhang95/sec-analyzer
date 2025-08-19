package com.secapp.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class QueryRequest {
  @NotBlank
  @Size(min = 2, max = 500)
  private String prompt;

  public String getPrompt() { return prompt; }
  public void setPrompt(String prompt) { this.prompt = prompt; }
}
