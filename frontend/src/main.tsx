import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ApolloClient, ApolloProvider, InMemoryCache } from '@apollo/client'
import createUploadLink from 'apollo-upload-client/createUploadLink.mjs'
import './index.css'
import App from './App.tsx'

const apolloClient = new ApolloClient({
  link: createUploadLink({
    uri: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/graphql',
  }),
  cache: new InMemoryCache(),
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ApolloProvider client={apolloClient}>
      <App />
    </ApolloProvider>
  </StrictMode>,
)
