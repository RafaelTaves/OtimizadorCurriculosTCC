# Objetivo
Crie um plano para criação de uma API para serviço de otimização de currículos baseado em IA, que utilize API da openai. Gere um plano.md, defina stacks de bibliotecas que serão utilizadas, a API será em python com FastAPI.

# Fluxo de Trabalho
1. Formulário de upload para arquivo PDF ou DOCX. 
2. Campo de texto para a descrição da vaga (Job Description). 
3. Extrair texto do currículo usando biblioteca como pdf-parse ou outra disponivel para python. 
4. Enviar o texto extraído junto com a descrição da vaga para um prompt de sistema que atue como um especialista em ATS e recrutamento. 
5. Instruir o modelo a reescrever o currículo mantendo a honestidade, mas focando em palavras-chave presentes na descrição da vaga. 
6. O agente também irá receber um template padrão de código LaTeX e deve inserir as informações neste template, gerando um código LaTex como saída. 
7. Este código sera transformado em um PDF e disponibilizado para o usuario poder alterar.  

# Banco de Dados
O banco de dados deve ser minimalista, apenas para logar tentativas e gerenciar limites de uso. Já existem duas entidades definidas, visivel na imagem C:\Users\rafae\Desktop\Programacao\Tcc\Documentação\DiagramaDeClasse.png. Se necessário criar mais entidades para monitorar o sistema informe.
