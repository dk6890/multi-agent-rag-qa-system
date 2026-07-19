package com.example.rag.controller;

import com.example.rag.common.ApiResponse;
import com.example.rag.dto.ChatAskRequest;
import com.example.rag.service.ChatService;
import com.example.rag.vo.ChatAskVO;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/chat")
public class ChatController {

    private final ChatService chatService;

    public ChatController(ChatService chatService) {
        this.chatService = chatService;
    }

    @PostMapping("/ask")
    public ApiResponse<ChatAskVO> ask(@Valid @RequestBody ChatAskRequest request) {
        return ApiResponse.success(chatService.ask(request));
    }
}
