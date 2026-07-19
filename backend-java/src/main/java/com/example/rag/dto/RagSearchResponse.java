package com.example.rag.dto;

import java.util.ArrayList;
import java.util.List;

public class RagSearchResponse {

    private List<RagReferenceDTO> references = new ArrayList<>();

    public List<RagReferenceDTO> getReferences() {
        return references;
    }

    public void setReferences(List<RagReferenceDTO> references) {
        this.references = references;
    }
}
