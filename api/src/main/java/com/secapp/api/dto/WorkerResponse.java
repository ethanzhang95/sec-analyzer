package com.secapp.api.dto;

import java.util.List;

public class WorkerResponse {
  private boolean ok;
  private String answer;
  private List<String> citations;
  private String error;

  public boolean isOk() { return ok; }
  public void setOk(boolean ok) { this.ok = ok; }
  public String getAnswer() { return answer; }
  public void setAnswer(String answer) { this.answer = answer; }
  public List<String> getCitations() { return citations; }
  public void setCitations(List<String> citations) { this.citations = citations; }
  public String getError() { return error; }
  public void setError(String error) { this.error = error; }
}
