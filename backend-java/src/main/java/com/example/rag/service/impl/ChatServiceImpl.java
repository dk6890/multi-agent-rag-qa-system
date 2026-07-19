package com.example.rag.service.impl;

import com.example.rag.client.LlmClient;
import com.example.rag.client.PythonRagClient;
import com.example.rag.common.ApiResponse;
import com.example.rag.common.BusinessException;
import com.example.rag.common.ErrorCode;
import com.example.rag.common.MessageRole;
import com.example.rag.dto.ChatAskRequest;
import com.example.rag.dto.RagReferenceDTO;
import com.example.rag.dto.RagSearchRequest;
import com.example.rag.dto.RagSearchResponse;
import com.example.rag.entity.QaMessage;
import com.example.rag.entity.QaReference;
import com.example.rag.entity.QaSession;
import com.example.rag.mapper.KnowledgeFileMapper;
import com.example.rag.mapper.QaMessageMapper;
import com.example.rag.mapper.QaReferenceMapper;
import com.example.rag.mapper.QaSessionMapper;
import com.example.rag.service.ChatService;
import com.example.rag.vo.ChatAskVO;
import com.example.rag.vo.ReferenceVO;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@Service
public class ChatServiceImpl implements ChatService {

    private static final int DEFAULT_TOP_K = 5;

    private final QaSessionMapper qaSessionMapper;
    private final QaMessageMapper qaMessageMapper;
    private final QaReferenceMapper qaReferenceMapper;
    private final KnowledgeFileMapper knowledgeFileMapper;
    private final PythonRagClient pythonRagClient;
    private final LlmClient llmClient;
    private final ObjectMapper objectMapper;

    public ChatServiceImpl(QaSessionMapper qaSessionMapper,
                           QaMessageMapper qaMessageMapper,
                           QaReferenceMapper qaReferenceMapper,
                           KnowledgeFileMapper knowledgeFileMapper,
                           PythonRagClient pythonRagClient,
                           LlmClient llmClient,
                           ObjectMapper objectMapper) {
        this.qaSessionMapper = qaSessionMapper;
        this.qaMessageMapper = qaMessageMapper;
        this.qaReferenceMapper = qaReferenceMapper;
        this.knowledgeFileMapper = knowledgeFileMapper;
        this.pythonRagClient = pythonRagClient;
        this.llmClient = llmClient;
        this.objectMapper = objectMapper;
    }

    @Override
    @Transactional
    public ChatAskVO ask(ChatAskRequest request) {
        if (request == null || !StringUtils.hasText(request.getQuestion())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "问题不能为空");
        }
        Long sessionId = ensureSession(request);
        saveMessage(sessionId, MessageRole.USER, request.getQuestion());

        ApiResponse<RagSearchResponse> searchResponse = pythonRagClient.search(
                new RagSearchRequest(request.getQuestion(), DEFAULT_TOP_K));
        if (searchResponse == null || !Integer.valueOf(200).equals(searchResponse.getCode())) {
            String msg = searchResponse == null ? "Python RAG 返回为空" : searchResponse.getMsg();
            throw new BusinessException(ErrorCode.PYTHON_RAG_ERROR, msg);
        }

        List<ReferenceVO> references = filterExistingFileReferences(toReferenceVOList(searchResponse.getData()));
        String answer = llmClient.generateAnswer(request.getQuestion(), references);
        QaMessage assistantMessage = saveMessage(sessionId, MessageRole.ASSISTANT, answer);
        saveReferences(assistantMessage.getId(), references);

        ChatAskVO vo = new ChatAskVO();
        vo.setSessionId(sessionId);
        vo.setQuestion(request.getQuestion());
        vo.setAnswer(answer);
        vo.setReferences(references);
        return vo;
    }

    private Long ensureSession(ChatAskRequest request) {
        if (request.getSessionId() != null) {
            QaSession existing = qaSessionMapper.selectById(request.getSessionId());
            if (existing == null) {
                throw new BusinessException(ErrorCode.NOT_FOUND, "会话不存在");
            }
            existing.setUpdatedAt(LocalDateTime.now());
            qaSessionMapper.updateById(existing);
            return existing.getId();
        }
        LocalDateTime now = LocalDateTime.now();
        QaSession session = new QaSession();
        session.setTitle(buildSessionTitle(request.getQuestion()));
        session.setCreatedAt(now);
        session.setUpdatedAt(now);
        qaSessionMapper.insert(session);
        return session.getId();
    }

    private QaMessage saveMessage(Long sessionId, MessageRole role, String content) {
        QaMessage message = new QaMessage();
        message.setSessionId(sessionId);
        message.setRole(role.name());
        message.setContent(content);
        message.setCreatedAt(LocalDateTime.now());
        qaMessageMapper.insert(message);
        return message;
    }

    private List<ReferenceVO> toReferenceVOList(RagSearchResponse searchResponse) {
        if (searchResponse == null || searchResponse.getReferences() == null) {
            return new ArrayList<>();
        }
        return searchResponse.getReferences().stream().map(this::toReferenceVO).toList();
    }

    private List<ReferenceVO> filterExistingFileReferences(List<ReferenceVO> references) {
        return references.stream()
                .filter(reference -> reference.getFileId() != null
                        && knowledgeFileMapper.selectById(reference.getFileId()) != null)
                .toList();
    }

    private ReferenceVO toReferenceVO(RagReferenceDTO dto) {
        ReferenceVO vo = new ReferenceVO();
        vo.setFileId(dto.getFileId());
        vo.setFileName(dto.getFileName());
        vo.setChunkText(dto.getChunkText());
        vo.setScore(dto.getScore() == null ? BigDecimal.ZERO : dto.getScore());
        vo.setChunkId(dto.getChunkId());
        vo.setMetadata(dto.getMetadata());
        return vo;
    }

    private void saveReferences(Long messageId, List<ReferenceVO> references) {
        for (ReferenceVO reference : references) {
            QaReference entity = new QaReference();
            entity.setMessageId(messageId);
            entity.setFileId(reference.getFileId());
            entity.setFileName(reference.getFileName());
            entity.setChunkId(reference.getChunkId());
            entity.setChunkText(reference.getChunkText());
            entity.setScore(reference.getScore() == null ? BigDecimal.ZERO : reference.getScore());
            entity.setMetadata(toJson(reference.getMetadata()));
            entity.setCreatedAt(LocalDateTime.now());
            qaReferenceMapper.insert(entity);
        }
    }

    private String toJson(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new BusinessException(ErrorCode.INTERNAL_ERROR, "引用 metadata 序列化失败");
        }
    }

    private String buildSessionTitle(String question) {
        String normalized = question.trim();
        if (normalized.length() <= 30) {
            return normalized;
        }
        return normalized.substring(0, 30);
    }
}
