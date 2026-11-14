import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());

// jsdom does not implement these.
Element.prototype.scrollIntoView = () => {};
