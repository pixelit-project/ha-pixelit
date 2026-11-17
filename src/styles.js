// Copyright (c) 2026 Pissbirne and PixelIt project contributors. MIT license.
import { css } from "lit";

export const editorStyles = css`
  :host {
    display: block;
  }
  ha-form {
    display: block;
  }
`;

export const cardStyles = css`
  :host {
    display: block;
    min-width: 0;
  }
  ha-card {
    overflow: hidden;
  }
  .plc-content[role="button"] {
    cursor: pointer;
  }
  .plc-content:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  ha-card.transparent {
    background: transparent;
    box-shadow: none;
    border: none;
  }
  .plc-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    padding: 0 16px 16px;
  }
  .plc-controls button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: 1px solid var(--divider-color);
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    cursor: pointer;
  }
  .plc-controls button[aria-pressed="true"] {
    color: var(--primary-color);
  }
  .plc-controls button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .plc-brightness {
    display: flex;
    align-items: center;
    flex: 1;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 12px;
    color: var(--secondary-text-color);
  }
  .plc-brightness input {
    min-width: 80px;
    flex: 1;
    accent-color: var(--primary-color);
  }
  .plc-control-error {
    flex-basis: 100%;
    font-size: 12px;
    color: var(--error-color);
    overflow-wrap: anywhere;
  }
  .plc-inner {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    container-type: inline-size;
    min-width: 0;
  }
  .plc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    min-width: 0;
  }
  .plc-title {
    font-size: var(--ha-font-size-l, 16px);
    font-weight: 500;
    color: var(--primary-text-color);
    overflow-wrap: anywhere;
    min-width: 0;
  }
  .plc-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--primary-text-color);
    font-size: 12px;
    line-height: 20px;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 500;
    margin-inline-start: auto;
    white-space: nowrap;
  }
  .plc-status.ok {
    background: rgba(76, 175, 80, 0.2);
  }
  .plc-status.err {
    background: rgba(244, 67, 54, 0.2);
  }
  .plc-status::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--success-color, #4caf50);
  }
  .plc-status.err::before {
    background: var(--error-color, #f44336);
  }
  .plc-grid {
    display: grid;
    width: 100%;
    align-self: stretch;
    min-width: 0;
    background: #000;
    border-radius: 4px;
    overflow: hidden;
  }
  .px {
    aspect-ratio: 1/1;
    border-radius: 1px;
  }
  .plc-empty {
    font-size: 12px;
    color: var(--secondary-text-color);
    padding: 8px 0;
  }
`;
