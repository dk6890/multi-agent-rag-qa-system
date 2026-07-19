package com.example.rag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.rag.client.PythonRagClient;
import com.example.rag.common.ApiResponse;
import com.example.rag.common.BusinessException;
import com.example.rag.common.ErrorCode;
import com.example.rag.common.FileStatus;
import com.example.rag.config.RagProperties;
import com.example.rag.dto.RagIndexRequest;
import com.example.rag.dto.RagIndexResponse;
import com.example.rag.entity.KnowledgeFile;
import com.example.rag.mapper.KnowledgeFileMapper;
import com.example.rag.service.FileService;
import com.example.rag.vo.FileListVO;
import com.example.rag.vo.FileUploadVO;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

@Service
public class FileServiceImpl implements FileService {

    private final KnowledgeFileMapper knowledgeFileMapper;
    private final PythonRagClient pythonRagClient;
    private final RagProperties properties;

    public FileServiceImpl(KnowledgeFileMapper knowledgeFileMapper,
                           PythonRagClient pythonRagClient,
                           RagProperties properties) {
        this.knowledgeFileMapper = knowledgeFileMapper;
        this.pythonRagClient = pythonRagClient;
        this.properties = properties;
    }

    @Override
    @Transactional
    public FileUploadVO upload(MultipartFile file) {
        validateFile(file);
        SavedFile savedFile = saveFile(file);
        LocalDateTime now = LocalDateTime.now();

        KnowledgeFile knowledgeFile = new KnowledgeFile();
        knowledgeFile.setFileName(savedFile.originalFileName());
        knowledgeFile.setFileType(savedFile.fileType());
        knowledgeFile.setFileSize(file.getSize());
        knowledgeFile.setFilePath(savedFile.path().toString());
        knowledgeFile.setStatus(FileStatus.UPLOADED.name());
        knowledgeFile.setChunkCount(0);
        knowledgeFile.setCreatedAt(now);
        knowledgeFile.setUpdatedAt(now);
        knowledgeFileMapper.insert(knowledgeFile);

        updateStatus(knowledgeFile, FileStatus.PROCESSING, 0, null);
        try {
            ApiResponse<RagIndexResponse> response = pythonRagClient.index(
                    new RagIndexRequest(knowledgeFile.getId(), knowledgeFile.getFilePath(), knowledgeFile.getFileName()));
            if (response != null && Integer.valueOf(200).equals(response.getCode()) && response.getData() != null) {
                Integer chunkCount = response.getData().getChunkCount() == null ? 0 : response.getData().getChunkCount();
                updateStatus(knowledgeFile, FileStatus.SUCCESS, chunkCount, null);
            } else {
                String msg = response == null ? "Python RAG 返回为空" : response.getMsg();
                updateStatus(knowledgeFile, FileStatus.FAILED, 0, msg);
            }
        } catch (BusinessException ex) {
            updateStatus(knowledgeFile, FileStatus.FAILED, 0, ex.getMessage());
        }

        return new FileUploadVO(knowledgeFile.getId(), knowledgeFile.getFileName(), knowledgeFile.getStatus());
    }

    @Override
    public List<FileListVO> listFiles() {
        List<KnowledgeFile> files = knowledgeFileMapper.selectList(
                new QueryWrapper<KnowledgeFile>().orderByDesc("created_at"));
        return files.stream().map(this::toFileListVO).toList();
    }

    private void validateFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "文件不能为空");
        }
        if (file.getSize() > properties.getMaxFileSize()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "文件大小超过限制");
        }
        String originalFileName = file.getOriginalFilename();
        if (!StringUtils.hasText(originalFileName)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "文件名不能为空");
        }
        String cleanName = StringUtils.cleanPath(originalFileName);
        if (cleanName.contains("..") || cleanName.contains("/") || cleanName.contains("\\")) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "文件名不安全");
        }
        String fileType = extractFileType(cleanName);
        boolean allowed = properties.getAllowedFileTypes().stream()
                .anyMatch(type -> type.equalsIgnoreCase(fileType));
        if (!allowed) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "文件类型不支持");
        }
    }

    private SavedFile saveFile(MultipartFile file) {
        String originalFileName = StringUtils.cleanPath(file.getOriginalFilename());
        String fileType = extractFileType(originalFileName);
        String storedFileName = UUID.randomUUID() + "." + fileType;
        try {
            Path uploadDir = Paths.get(properties.getUploadDir()).toAbsolutePath().normalize();
            Files.createDirectories(uploadDir);
            Path targetPath = uploadDir.resolve(storedFileName).normalize();
            if (!targetPath.startsWith(uploadDir)) {
                throw new BusinessException(ErrorCode.BAD_REQUEST, "文件保存路径不安全");
            }
            file.transferTo(targetPath);
            return new SavedFile(originalFileName, fileType, targetPath);
        } catch (IOException ex) {
            throw new BusinessException(ErrorCode.INTERNAL_ERROR, "文件保存失败: " + ex.getMessage());
        }
    }

    private String extractFileType(String fileName) {
        int dotIndex = fileName.lastIndexOf('.');
        if (dotIndex < 0 || dotIndex == fileName.length() - 1) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "文件类型不支持");
        }
        return fileName.substring(dotIndex + 1).toLowerCase(Locale.ROOT);
    }

    private void updateStatus(KnowledgeFile knowledgeFile, FileStatus status, Integer chunkCount, String errorMsg) {
        knowledgeFile.setStatus(status.name());
        knowledgeFile.setChunkCount(chunkCount);
        knowledgeFile.setErrorMsg(errorMsg);
        knowledgeFile.setUpdatedAt(LocalDateTime.now());
        knowledgeFileMapper.updateById(knowledgeFile);
    }

    private FileListVO toFileListVO(KnowledgeFile file) {
        FileListVO vo = new FileListVO();
        vo.setFileId(file.getId());
        vo.setFileName(file.getFileName());
        vo.setFileType(file.getFileType());
        vo.setFileSize(file.getFileSize());
        vo.setStatus(file.getStatus());
        vo.setChunkCount(file.getChunkCount());
        vo.setErrorMsg(file.getErrorMsg());
        vo.setCreatedAt(file.getCreatedAt());
        vo.setUpdatedAt(file.getUpdatedAt());
        return vo;
    }

    private record SavedFile(String originalFileName, String fileType, Path path) {
    }
}
