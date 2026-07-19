package com.example.rag.service;

import com.example.rag.dto.ChatAskRequest;
import com.example.rag.vo.ChatAskVO;

public interface ChatService {

    ChatAskVO ask(ChatAskRequest request);
}
