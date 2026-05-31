/**
 * Application entry point.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1890ff',
          borderRadius: 4,
          fontSize: 13,
        },
        components: {
          Button: {
            controlHeight: 30,
          },
          Tabs: {
            cardPadding: '6px 10px',
          },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
