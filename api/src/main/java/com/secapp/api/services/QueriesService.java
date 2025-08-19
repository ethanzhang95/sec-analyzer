package com.secapp.api.services;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.secapp.api.dto.QueryRequest;
import com.secapp.api.dto.WorkerResponse;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

@Service
public class QueriesService {
  private final ObjectMapper mapper = new ObjectMapper();

  public WorkerResponse runPrompt(QueryRequest req) {
    try {
      Path apiDir = Paths.get("").toAbsolutePath();                 // .../SECapp/api
      Path workerDir = apiDir.getParent().resolve("worker_py");     // .../SECapp/worker_py

      Path venvPy = workerDir.resolve(".venv/bin/python");
      String python = Files.isExecutable(venvPy) ? venvPy.toString() : "python3";

      List<String> cmd = new ArrayList<>();
      cmd.add(python);
      cmd.add("app/run_query.py");
      cmd.add("--prompt");
      cmd.add(req.getPrompt());

      ProcessBuilder pb = new ProcessBuilder(cmd);
      pb.directory(workerDir.toFile());
      pb.redirectErrorStream(false); // keep stdout (JSON) separate from stderr (logs)

      Process p = pb.start();

      // Drain stderr (logs) in background so the process can't block
      new Thread(() -> {
        try (BufferedReader er = new BufferedReader(
            new InputStreamReader(p.getErrorStream(), StandardCharsets.UTF_8))) {
          String line;
          while ((line = er.readLine()) != null) {
            System.out.println("[worker stderr] " + line);
          }
        } catch (IOException ignored) {}
      }).start();

      // Read ONLY stdout (should be a single JSON object)
      String out;
      try (BufferedReader br = new BufferedReader(
          new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) sb.append(line);
        out = sb.toString();
      }

      boolean finished = p.waitFor(Duration.ofMinutes(6).toMillis(),
                                   java.util.concurrent.TimeUnit.MILLISECONDS);
      if (!finished) {
        p.destroyForcibly();
        return error("Worker timed out");
      }

      String trimmed = out.trim();
      if (trimmed.isEmpty()) return error("Worker returned empty output");

      System.out.println("[worker stdout] " +
          (trimmed.length() > 400 ? trimmed.substring(0, 400) + "..." : trimmed));

      char first = trimmed.charAt(0);
      if (first == '{') {
        return mapper.readValue(trimmed, WorkerResponse.class);
      } else if (first == '[') {
        // Fallback: if the worker ever prints an array, wrap as citations
        JsonNode arr = mapper.readTree(trimmed);
        WorkerResponse r = new WorkerResponse();
        r.setOk(true);
        if (arr.isArray()) {
          List<String> cites = new ArrayList<>();
          for (JsonNode n : arr) if (n.isTextual()) cites.add(n.asText());
          r.setCitations(cites.isEmpty() ? null : cites);
        }
        return r;
      } else {
        return error("Worker did not return JSON (starts with: " + first + ")");
      }
    } catch (Exception e) {
      return error("Worker failed: " + e.getMessage());
    }
  }

  private WorkerResponse error(String msg) {
    WorkerResponse r = new WorkerResponse();
    r.setOk(false);
    r.setError(msg);
    return r;
  }
}
