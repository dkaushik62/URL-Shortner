package com.urlshortner.urls;

import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;

@Service
public class UrlService {
    public static final class UnknownCode extends RuntimeException {}
    public static final class AllocationExhausted extends RuntimeException {}

    private final UrlRepository repository;
    private final CodeGenerator codes;

    public UrlService(UrlRepository repository, CodeGenerator codes) {
        this.repository = repository;
        this.codes = codes;
    }

    // Deliberately no surrounding transaction: PostgreSQL uniqueness failures
    // must not leave subsequent allocation attempts in an aborted transaction.
    public UrlRepository.StoredUrl create(String url) {
        if (!Destination.valid(url)) throw new IllegalArgumentException("Invalid destination");
        for (int attempt = 0; attempt < 5; attempt++) {
            try {
                return repository.insert(codes.next(), url);
            } catch (DataAccessException exception) {
                if (!UrlRepository.isCodeConflict(exception)) throw exception;
            }
        }
        throw new AllocationExhausted();
    }

    public String redirect(String code) {
        return repository.recordRedirect(code).orElseThrow(UnknownCode::new);
    }

    public UrlRepository.StoredUrl analytics(String code) {
        return repository.find(code).orElseThrow(UnknownCode::new);
    }
}
