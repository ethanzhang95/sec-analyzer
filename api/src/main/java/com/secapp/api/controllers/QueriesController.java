package com.secapp.api.controllers;

import com.secapp.api.dto.QueryRequest;
import com.secapp.api.dto.WorkerResponse;
import com.secapp.api.services.QueriesService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/queries")
@CrossOrigin(origins = {"http://localhost:3000", "http://localhost:5173"})
public class QueriesController {

  private final QueriesService service;

  public QueriesController(QueriesService service) {
    this.service = service;
  }

  @GetMapping("/health")
  public String health() {
    return "OK";
  }

  @PostMapping
  public ResponseEntity<WorkerResponse> create(@Valid @RequestBody QueryRequest req) {
    System.out.println("Received POST /queries with prompt: " + req.getPrompt()); // Add this line
    WorkerResponse resp = service.runPrompt(req);
    return ResponseEntity.ok(resp);
  }
}
