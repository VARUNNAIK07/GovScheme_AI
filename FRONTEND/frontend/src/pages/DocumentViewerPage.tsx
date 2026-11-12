// frontend/src/pages/DocumentViewerPage.tsx
import React, { useState, useEffect, useRef } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import * as pdfjsLib from 'pdfjs-dist';
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  ExternalLink,
  Info,
  Quote,
} from 'lucide-react';
import { citationsApi } from '../api/endpoints';
import { getAuthToken } from '../api/client';
import { LoadingState, ErrorState } from '../components/States';
import type { CitationTarget } from '../types/contracts';

// Configure pdfjs worker to local bundled worker
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';

export const DocumentViewerPage: React.FC = () => {
  const { doc_id } = useParams<{ doc_id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialPage = parseInt(searchParams.get('page') || '1', 10);
  const citationId = searchParams.get('citation_id');

  const [currentPage, setCurrentPage] = useState<number>(initialPage);
  const [numPages, setNumPages] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.25);
  const [citation, setCitation] = useState<CitationTarget | null>(null);
  const [pdfDoc, setPdfDoc] = useState<any>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [pageRendering, setPageRendering] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const highlightOverlayRef = useRef<HTMLDivElement | null>(null);

  // 1. Fetch citation metadata if citation_id is present
  useEffect(() => {
    if (!citationId) return;

    citationsApi
      .get(citationId)
      .then((target) => {
        setCitation(target);
        if (target.page && target.page !== currentPage) {
          setCurrentPage(target.page);
        }
      })
      .catch(() => {
        // Citation unknown: still show the document, just without a highlight
        setCitation(null);
      });
  }, [citationId, doc_id]);

  // 2. Load the PDF document
  useEffect(() => {
    let isCancelled = false;
    let activeTask: any = null;
    let activeDoc: any = null;
    setLoading(true);
    setError(null);

    if (!doc_id) {
      setError('No document selected.');
      setLoading(false);
      return;
    }

    const token = getAuthToken();
    const pdfUrl = citationsApi.getDocumentFileUrl(doc_id);

    fetch(pdfUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Failed to load document (${res.status} ${res.statusText})`);
        }
        return res.arrayBuffer();
      })
      .then((arrayBuffer) => {
        if (isCancelled) return null;
        activeTask = pdfjsLib.getDocument({
          data: arrayBuffer,
          cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/cmaps/',
          cMapPacked: true,
        });
        return activeTask.promise;
      })
      .then((loadedPdf) => {
        if (!loadedPdf || isCancelled) {
          loadedPdf?.destroy();
          return;
        }
        activeDoc = loadedPdf;
        setPdfDoc(loadedPdf);
        setNumPages(loadedPdf.numPages);
        setCurrentPage((p) => Math.min(Math.max(1, p), loadedPdf.numPages));
        setLoading(false);
      })
      .catch((err) => {
        if (isCancelled) return;
        setError(`Unable to load the source PDF: ${err?.message || 'unknown error'}`);
        setLoading(false);
      });

    return () => {
      isCancelled = true;
      try {
        activeTask?.destroy();
        activeDoc?.destroy();
      } catch {
        // ignore cleanup errors on unmount
      }
    };
  }, [doc_id]);

  // 3. Render the active page on canvas
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let isRenderCancelled = false;
    let renderTask: any = null;
    setPageRendering(true);

    pdfDoc
      .getPage(currentPage)
      .then((page: any) => {
        if (isRenderCancelled) return;

        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        if (!canvas) return;

        const context = canvas.getContext('2d');
        if (!context) return;

        canvas.height = viewport.height;
        canvas.width = viewport.width;

        // Only one render may use the canvas at a time; the cleanup below cancels a stale one
        renderTask = page.render({ canvasContext: context, viewport });
        return renderTask.promise.then(() => {
          if (isRenderCancelled) return;
          setPageRendering(false);
          drawHighlight(viewport, page);
        });
      })
      .catch((err: any) => {
        if (isRenderCancelled || err?.name === 'RenderingCancelledException') return;
        setError(`Error rendering page: ${err?.message || 'unknown error'}`);
        setPageRendering(false);
      });

    return () => {
      isRenderCancelled = true;
      renderTask?.cancel();
    };
  }, [pdfDoc, currentPage, scale, citation]);

  // 4. Draw bounding box highlight overlay
  const drawHighlight = (viewport: any, page: any) => {
    const overlay = highlightOverlayRef.current;
    if (!overlay) return;

    overlay.innerHTML = '';
    if (!citation || citation.precision !== 'passage' || !citation.bbox) {
      return;
    }

    // Only draw highlight if the cited page matches current page
    if (citation.page !== currentPage) return;

    const [x0, y0, x1, y1] = citation.bbox;

    // Convert PDF points coordinates to canvas viewport coordinates
    // PDF coordinates have origin at bottom-left. Docling bbox points [x0, y0, x1, y1]
    const pageView = page.view; // [0, 0, width, height]
    const pageHeight = pageView ? pageView[3] : 842;

    const left = x0 * scale;
    // PDF origin: (0,0) at bottom-left, y0 is lower, y1 is upper in standard coords
    // If Docling gives bottom-up coords:
    const top = (pageHeight - Math.max(y0, y1)) * scale;
    const width = Math.abs(x1 - x0) * scale;
    const height = Math.abs(y1 - y0) * scale;

    const box = document.createElement('div');
    box.className = 'pdf-highlight-box';
    box.style.left = `${Math.max(0, left)}px`;
    box.style.top = `${Math.max(0, top)}px`;
    box.style.width = `${Math.max(20, width)}px`;
    box.style.height = `${Math.max(16, height)}px`;
    box.setAttribute('role', 'mark');
    box.setAttribute('aria-label', 'Verified evidence passage');

    overlay.appendChild(box);
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= numPages) {
      setCurrentPage(newPage);
      setSearchParams((prev) => {
        prev.set('page', newPage.toString());
        return prev;
      });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
        <LoadingState message="Loading source document and verifying passage coordinates..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <ErrorState
          title="Document Viewer Error"
          message={error}
          onRetry={() => window.location.reload()}
        />
      </div>
    );
  }

  const isPassagePrecision = citation?.precision === 'passage';

  return (
    <div className="space-y-4 max-w-6xl mx-auto">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
        <div className="flex items-center gap-3">
          <Link
            to="/library"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-700 hover:text-slate-900 px-2.5 py-1.5 rounded border border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Schemes</span>
          </Link>
          <div className="h-4 w-px bg-slate-200 hidden sm:block" />
          <span className="text-xs font-medium text-slate-600 truncate max-w-xs">
            Doc ID: <code className="text-gov-800 font-semibold">{doc_id}</code>
          </span>
        </div>

        {/* Zoom & Page Controls */}
        <div className="flex items-center gap-2">
          <div className="flex items-center border border-slate-300 rounded-md bg-white">
            <button
              type="button"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1 || pageRendering}
              className="p-1.5 text-slate-600 hover:text-slate-900 disabled:opacity-30"
              aria-label="Previous Page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 text-xs font-medium text-slate-700 tabular-nums">
              Page {currentPage} of {numPages}
            </span>
            <button
              type="button"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= numPages || pageRendering}
              className="p-1.5 text-slate-600 hover:text-slate-900 disabled:opacity-30"
              aria-label="Next Page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center border border-slate-300 rounded-md bg-white">
            <button
              type="button"
              onClick={() => setScale((s) => Math.max(0.75, s - 0.2))}
              className="p-1.5 text-slate-600 hover:text-slate-900"
              title="Zoom Out"
              aria-label="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="px-2 text-xs text-slate-600 tabular-nums">
              {Math.round(scale * 100)}%
            </span>
            <button
              type="button"
              onClick={() => setScale((s) => Math.min(2.5, s + 0.2))}
              className="p-1.5 text-slate-600 hover:text-slate-900"
              title="Zoom In"
              aria-label="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Precision Banner */}
      {!isPassagePrecision && (
        <div
          className="p-3.5 bg-amber-50 border border-amber-300 rounded-lg flex items-start gap-2.5 text-xs text-amber-900"
          role="status"
        >
          <Info className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
          <p className="font-medium">
            Exact passage position unavailable, showing the cited page
          </p>
        </div>
      )}

      {/* Citation Metadata Banner */}
      {citation && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-2 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-900">Citation:</span>
              <span className="font-mono bg-white px-2 py-0.5 rounded border border-slate-200 text-gov-800">
                {citation.citation_id}
              </span>
              <span className="text-slate-500">Version: {citation.doc_version}</span>
              <span className="text-slate-500 capitalize">Precision: {citation.precision}</span>
            </div>

            {citation.source_url && (
              <a
                href={citation.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-gov-700 hover:underline font-semibold"
              >
                <span>Official PDF Source</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>

          {citation.quote && (
            <div className="flex items-start gap-2 pt-1 border-t border-slate-200 text-slate-700 italic">
              <Quote className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" />
              <span>&ldquo;{citation.quote}&rdquo;</span>
            </div>
          )}
        </div>
      )}

      {/* Canvas Viewport Container */}
      <div className="bg-slate-200 border border-slate-300 rounded-lg p-4 sm:p-8 overflow-auto flex justify-center min-h-[600px]">
        <div className="relative shadow-md bg-white border border-slate-300">
          <canvas ref={canvasRef} className="block" />
          {/* Highlight bounding box overlay */}
          <div
            ref={highlightOverlayRef}
            className="absolute inset-0 pointer-events-none"
            aria-hidden="true"
          />
        </div>
      </div>
    </div>
  );
};
